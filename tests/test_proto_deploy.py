STORY = "FORGE-PROTO-1"

import http.client
import json
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid

import pytest


def _client(repo, gh, tmp_path):
    client = tmp_path / "client"
    remote = tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stderr
    return client


def _docker(*args, check=True):
    result = subprocess.run(["docker", *args], text=True, capture_output=True, timeout=180)
    if check and result.returncode:
        pytest.fail(f"docker {' '.join(args[:2])} failed:\n{result.stdout}\n{result.stderr}")
    return result


def test_10_new_client_deploys_only_after_migration(repo, gh, tmp_path, monkeypatch):
    if not shutil.which("docker"):
        pytest.skip("Docker daemon is required for the deployment lifecycle test")
    host = subprocess.run(["docker", "context", "inspect", "--format",
                           "{{.Endpoints.docker.Host}}"], text=True, capture_output=True, check=True).stdout.strip()
    docker_config = tmp_path / "docker-config"
    docker_config.mkdir()
    (docker_config / "config.json").write_text("{}")
    monkeypatch.setenv("DOCKER_CONFIG", str(docker_config))
    monkeypatch.setenv("DOCKER_HOST", host)
    if _docker("info", check=False).returncode:
        pytest.skip("Docker daemon is required for the deployment lifecycle test")
    client = _client(repo, gh, tmp_path)
    assert (client / "Dockerfile").is_file()
    assert len(list(client.rglob("Dockerfile"))) == 1
    assert "Dockerfile" in repo.git("ls-files", cwd=client).splitlines()
    (client / "frontend").mkdir()
    (client / "backend" / "prisma" / "migrations" / "20260928000000_init").mkdir(parents=True)
    (client / "package.json").write_text(json.dumps({
        "private": True, "workspaces": ["frontend", "backend"],
        "devDependencies": {"prisma": "6.19.1"}}))
    (client / "frontend" / "package.json").write_text(json.dumps({
        "name": "frontend", "version": "1.0.0", "scripts": {
            "build": "node -e \"require('fs').mkdirSync('dist',{recursive:true});require('fs').writeFileSync('dist/index.html','<h1>Prototype ready</h1>')\""}}))
    (client / "backend" / "package.json").write_text(json.dumps({
        "name": "backend", "version": "1.0.0", "scripts": {
            "build": "node -e \"require('fs').mkdirSync('dist',{recursive:true})\"",
            "start:prod": "node server.js"}}))
    (client / "backend" / "server.js").write_text(
        "const http=require('http'),fs=require('fs');"
        "http.createServer((req,res)=>{if(req.url==='/health'){res.end('ok');return;}"
        "res.setHeader('content-type','text/html');"
        "res.end(fs.readFileSync(require('path').join(__dirname,'../frontend/dist/index.html')));})"
        ".listen(process.env.PORT||3000,'0.0.0.0');\n")
    (client / "backend" / "prisma" / "schema.prisma").write_text(
        'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n'
        'generator client {\n  provider = "prisma-client-js"\n}\n'
        'model Ready {\n  id Int @id\n}\n')
    (client / "backend" / "prisma" / "migrations" / "migration_lock.toml").write_text(
        'provider = "postgresql"\n')
    (client / "backend" / "prisma" / "migrations" / "20260928000000_init" / "migration.sql").write_text(
        'CREATE TABLE "Ready" ("id" INTEGER NOT NULL PRIMARY KEY);\n')
    subprocess.run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit"],
                   cwd=client, capture_output=True, text=True, check=True, timeout=180)
    tag = "forge-proto-test-" + uuid.uuid4().hex[:12]
    network = tag + "-net"
    database = tag + "-db"
    success = tag + "-ok"
    failure = tag + "-fail"
    try:
        _docker("network", "create", network)
        _docker("run", "-d", "--name", database, "--network", network,
                "-e", "POSTGRES_PASSWORD=test", "-e", "POSTGRES_DB=prototype", "postgres:16-alpine")
        for _ in range(120):
            if _docker("exec", database, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                break
        else:
            pytest.fail("Postgres did not become ready")
        _docker("build", "-t", tag, str(client))
        url = "postgresql://postgres:test@" + database + ":5432/prototype"
        _docker("run", "-d", "--name", success, "--network", network,
                "-p", "127.0.0.1::3000", "-e", "DATABASE_URL=" + url, tag)
        published = _docker("port", success, "3000/tcp", check=False)
        if published.returncode:
            logs = _docker("logs", success)
            pytest.fail(published.stderr + logs.stdout + logs.stderr)
        port = published.stdout.strip().rsplit(":", 1)[1]
        # Poll the observable HTTP state, without a fixed sleep.
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    assert response.status == 200
                break
            except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected):
                if _docker("inspect", "-f", "{{.State.Running}}", success).stdout.strip() == "false":
                    logs = _docker("logs", success)
                    pytest.fail(logs.stdout + logs.stderr)
        else:
            pytest.fail(_docker("logs", success).stdout)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as response:
            assert b"Prototype ready" in response.read()
        assert "Ready" in _docker("exec", database, "psql", "-U", "postgres", "-d", "prototype",
                                  "-Atc", "SELECT to_regclass('public.\"Ready\"')").stdout
        _docker("run", "-d", "--name", failure, "--network", network,
                "-e", "DATABASE_URL=postgresql://postgres:wrong@" + database + ":5432/prototype", tag)
        result = _docker("wait", failure)
        assert result.stdout.strip() != "0"
        assert "Check DATABASE_URL" in _docker("logs", failure).stdout + _docker("logs", failure).stderr
    finally:
        for name in (success, failure, database):
            _docker("rm", "-f", name, check=False)
        _docker("network", "rm", network, check=False)
        _docker("image", "rm", tag, check=False)
