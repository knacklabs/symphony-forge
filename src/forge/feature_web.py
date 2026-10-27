"""Render a feature's web library and browser flows from the starter's marked projects files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge.feature_api import STARTER, _camel, _column, _pascal, _sample, _status_name, _status_type

LINK_PICKER = Path(__file__).parent / "templates/feature/link-picker.tsx"
# A mark is a `// forge:feature:<name>:start` line, or `{/* ... */}` inside JSX, up to its end line.
MARK = re.compile(r"^(?P<indent>[ \t]*)(?:// |\{/\* )forge:feature:(?P<name>[\w-]+):start(?: \*/\})?\n"
                  r".*?^[ \t]*(?:// |\{/\* )forge:feature:(?P=name):end(?: \*/\})?\n", re.M | re.S)
WEB_FILES = (
    "libs/projects/web/src/index.ts",
    "libs/projects/web/src/hooks/projects-hooks.ts",
    "libs/projects/web/src/hooks/projects-hooks.test.tsx",
    "libs/projects/web/src/pages/projects-page.tsx",
    "libs/projects/web/src/pages/project-detail-page.tsx",
    "libs/projects/web/src/pages/project-form-dialog.tsx",
    "apps/web/e2e/projects.spec.ts",
)


def taken_names() -> set[str]:
    """The names the starter's screens and flows declare, which a feature's own names must not repeat."""
    names = set()
    for path in WEB_FILES:
        text = (STARTER / path).read_text(encoding="utf-8")
        for match in re.finditer(r"\b(?:const|let|function)\s+(\w+)|\(\s*(\w+)\s*(?:\)\s*=>|:)|\(\{\s*([\w ,]+?)\s*\}", text):
            names |= {name.strip() for group in match.groups() if group for name in group.split(",")}
    return {name for name in names if "roject" not in name}


def _words(name: str) -> str:
    """`dueDate` reads `Due date`, `in-progress` reads `In progress`."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("-", " ").lower()
    return text[:1].upper() + text[1:]


def _plural(words: str) -> str:
    # ponytail: plain English plurals only (status, category, client), enough for filter labels.
    if words.endswith(("s", "x", "ch", "sh")):
        return words + "es"
    if words.endswith("y") and words[-2:-1] not in "aeiou":
        return words[:-1] + "ies"
    return words + "s"


def _js(value: Any) -> str:
    """A JavaScript literal, with strings in single quotes as the starter writes them."""
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return json.dumps(value)


def _attr(value: str) -> str:
    """A JSX attribute's text, in double quotes as the starter writes them."""
    return json.dumps(value, ensure_ascii=False)


def _labels_const(field: dict[str, Any]) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", _column(field)).upper() + "_LABELS"


def _rename(text: str, one: str, plural: str) -> str:
    """Rename projects: identifiers in camelCase, addresses and package names as slugs, text in words."""
    code = {"projects": _camel(plural), "Projects": _pascal(plural), "PROJECTS": plural.replace("-", "_").upper(),
            "project": _camel(one), "Project": _pascal(one), "PROJECT": one.replace("-", "_").upper()}
    plural_words, one_words = plural.replace("-", " "), one.replace("-", " ")
    words = {"projects": plural_words, "Projects": plural_words[:1].upper() + plural_words[1:],
             "project": one_words, "Project": one_words[:1].upper() + one_words[1:]}
    slugs = {"projects": plural, "project": one}
    pattern = re.compile(r"projects|Projects|PROJECTS|project|Project|PROJECT")

    def in_code(chunk: str) -> str:
        return pattern.sub(lambda m: slugs[m[0]] if m.start() and chunk[m.start() - 1] == "/" and m[0] in slugs
                           else code[m[0]], chunk)

    def in_text(chunk: str) -> str:
        def one_word(m: re.Match[str]) -> str:
            before, after = chunk[m.start() - 1:m.start()], chunk[m.end():m.end() + 2]
            if re.match(r"\w", before or " ") or re.match(r"\w", after[:1] or " "):
                return code[m[0]]  # part of a name, such as ProjectsPage in a comment
            if m[0] in slugs and (before in ("/", "-") or after[:1] == "-" or re.fullmatch(r"\.[a-z]", after)):
                return slugs[m[0]]
            return words.get(m[0], code[m[0]])
        return pattern.sub(one_word, chunk)

    out, i, start, n = [], 0, 0, len(text)
    while i < n:
        char = text[i]
        if text.startswith("//", i) or text.startswith("/*", i):
            end = text.find("\n", i) if text[i + 1] == "/" else text.find("*/", i) + 2
            end = n if end < 0 or end < i else end
            out += [in_code(text[start:i]), in_text(text[i:end])]
            i = start = end
        elif char == "/" and text[i + 1:i + 2] != ">" and re.search(r"[(,=:\[!&|?{};]\s*$|^\s*$", text[max(0, i - 80):i].split("\n")[-1]):
            # A regex literal: its text is renamed like a string, so an address keeps its slug.
            j, in_class = i + 1, False
            while j < n and (in_class or text[j] != "/") and text[j] != "\n":
                in_class = (in_class or text[j] == "[") and text[j] != "]"
                j += 2 if text[j] == "\\" else 1
            out += [in_code(text[start:i]), in_text(text[i:j + 1])]
            i = start = j + 1
        elif char in "'\"`":
            out.append(in_code(text[start:i]))
            j = i + 1
            while j < n and text[j] != char:
                j += 2 if text[j] == "\\" else 1
            # Template parts inside ${...} are code; this is enough for the starter's templates.
            literal = text[i:j + 1]
            out.append(re.sub(r"(\$\{[^}]*\})|([^$]+|\$)", lambda m: in_code(m[1]) if m[1] else in_text(m[2]), literal)
                       if char == "`" else in_text(literal))
            i = start = j + 1
        else:
            i += 1
    out.append(in_code(text[start:]))
    renamed = "".join(out)
    if plural_words != code["projects"] or one_words != code["project"]:
        # JSX text sits in code: give multi-word names their words there too.
        jsx_words = {code[key]: value for key, value in words.items()}
        renamed = re.sub(r"(?<=[>}])[^<>{}();=\n]*(?=[<{])", lambda m: re.sub(
            "|".join(sorted(map(re.escape, jsx_words), key=len, reverse=True)),
            lambda w: jsx_words[w[0]], m[0]), renamed)
    return renamed


def _replace_mark(text: str, name: str, body: str) -> str:
    matches = [match for match in MARK.finditer(text) if match["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"The projects starter needs one {name} feature mark.")
    match = matches[0]
    lines = [match["indent"] + line if line else "" for line in body.rstrip("\n").splitlines()]
    return text[:match.start()] + "".join(line + "\n" for line in lines) + text[match.end():]


class _Web:
    """The generated text for each mark, from the feature's fields and the kind table."""

    def __init__(self, fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any],
                 link_names: dict[str, str]):
        self.fields, self.one, self.plural, self.kinds = fields, one, plural, kinds["kinds"]
        self.model, self.item = _pascal(one), _camel(one)
        self.full_kinds = kinds
        self.link_names = link_names
        self.name = next(field for field in fields if field["kind"] == "text" and not field.get("optional"))
        self.search = next(field for field in fields if field["kind"] in ("text", "email"))
        self.statuses = [field for field in fields if field["kind"] == "status"]
        self.filters = [field for field in fields if self.kinds[field["kind"]]["filter_options"]]
        self.columns = [field for field in fields if field is self.name or self.kinds[field["kind"]]["column"]]
        self.links = [field for field in fields if field["kind"] == "link"]

    def kind(self, field: dict[str, Any], key: str) -> Any:
        return self.kinds[field["kind"]][key]

    def options(self, field: dict[str, Any]) -> list[str]:
        label = _words(field["target"] if field["kind"] == "link" else field["name"])
        plural = field["target"].replace("-", " ") if field["kind"] == "link" else _plural(label.lower())
        return [template.format(Label=label, label=label.lower(), labels=plural)
                for template in self.kind(field, "filter_options")]

    def link_target(self, field: dict[str, Any]) -> str:
        return f"path={_attr(field['target'])} nameField={_attr(self.link_names[field['target']])}"

    def link_props(self, field: dict[str, Any]) -> str:
        return (f"{self.link_target(field)} label={_attr(_words(field['name']))} "
                f"noun={_attr(field['target'].replace('-', ' '))}")

    # The value as the person reads it on the list and the detail screen.
    def shown(self, field: dict[str, Any], value: str) -> str:
        cell = self.kind(field, "cell")
        if cell == "badge":
            return f"{_labels_const(field)}[{value}]"
        if cell == "money":
            return f"formatMoney(String({value} / 100), DEFAULT_CURRENCY)"
        if cell == "number":
            return f"numberText({value})"
        if cell == "date":
            return f"formatDate({value}, 'UTC')"
        if cell == "yes-no":
            return f"{value} ? 'Yes' : 'No'"
        return value

    def util_imports(self, fields: list[dict[str, Any]], always: set[str]) -> str:
        names = set(always)
        for field in fields:
            cell = self.kind(field, "cell")
            names |= {"money": {"formatMoney", "DEFAULT_CURRENCY"}, "number": {"formatNumber"},
                      "date": {"formatDate"}}.get(cell, set())
        return f"import {{ {', '.join(sorted(names, key=str.lower))} }} from '@app/shared-util';"

    def number_helper(self) -> str:
        if not any(self.kind(field, "cell") == "number" for field in self.fields):
            return ""
        return ("\n/** A number as the API keeps it, with its own decimals: 42.5000 shows as 42.5. */\n"
                "export function numberText(value: string): string {\n"
                "  return formatNumber(Number(value), value.replace(/^[^.]*\\.?/, '').replace(/0+$/, '').length);\n}\n")

    def contract_imports(self, *names: str) -> str:
        return f"import {{ {', '.join(names)} }} from '@app/{self.plural}-contracts';"

    # The list page.
    def list_imports(self) -> str:
        names = [_status_name(self.one, field) for field in self.statuses]
        names += [f"type {self.model}", f"type {self.model}Input"]
        names += [f"type {_status_type(self.one, field)}" for field in self.statuses]
        lines = [self.util_imports(self.columns, {"formatDate", "formatNumber"}), self.contract_imports(*names)]
        # numberText lives here for the detail screen too, so the list imports formatNumber always.
        if any(field["kind"] in ("status", "yes-no") for field in self.filters):
            lines.append("import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';")
        link_names = [name for name, used in (("LinkedName", any(field["kind"] == "link" for field in self.columns)),
                                              ("LinkPicker", any(field["kind"] == "link" for field in self.filters))) if used]
        if link_names:
            lines.append(f"import {{ {', '.join(link_names)} }} from './link-picker';")
        return "\n".join(lines)

    def list_fields(self) -> str:
        sort_keys = [_column(field) for field in self.fields if field["kind"] != "long-text"]
        lines = [
            f"const SORT_KEYS: {self.model}SortBy[] = [{', '.join(map(_js, sort_keys + ['createdAtUtc', 'updatedAtUtc']))}];",
            "/** The list's filters other than the search and Show deleted. */",
            f"const FILTER_KEYS: (keyof {self.model}ListQuery)[] = [{', '.join(_js(_column(field)) for field in self.filters)}];",
            f"const SEARCH_PLACEHOLDER = {_js('Search by ' + _words(self.search['name']).lower())};",
        ]
        for field in self.statuses:
            labels = ", ".join(f"{option if re.fullmatch(r'[a-z][a-z0-9]*', option) else _js(option)}: {_js(_words(option))}"
                               for option in field["options"])
            lines.append(f"export const {_labels_const(field)}: Record<{_status_type(self.one, field)}, string> = {{ {labels} }};")
        return "\n".join(lines) + self.number_helper()

    def read_filters(self) -> str:
        lines = []
        for field in self.filters:
            column = _column(field)
            if field["kind"] == "status":
                lines.append(f"{column}: {_status_name(self.one, field)}.safeParse(params.get('{column}')).data,")
            elif field["kind"] == "yes-no":
                lines.append(f"{column}: (['yes', 'no'] as const).find((value) => value === params.get('{column}')),")
            else:
                lines.append(f"{column}: params.get('{column}') || undefined,")
        return "\n".join(lines)

    def columns_body(self) -> str:
        blocks = []
        for field in self.columns:
            column, label, cell = _column(field), _words(field["name"]), self.kind(field, "cell")
            value = f"row.original.{column}"
            right = cell == "money"
            button = [f"<Button variant=\"ghost\" size=\"sm\" className=\"{'-mr-3 ml-auto' if right else '-ml-3'} h-8 gap-2\" "
                      f"onClick={{() => column.toggleSorting(column.getIsSorted() === 'asc')}}>",
                      f"  <SortLabel label={_attr(label)} sorted={{column.getIsSorted()}} />", "</Button>"]
            if right:
                button = ["<div className=\"flex\">", *("  " + line for line in button), "</div>"]
            header = "\n    ".join(button)
            if field is self.name:
                body = (f"(\n    <span className=\"inline-flex items-center gap-2\">\n"
                        f"      <Link className=\"font-medium underline-offset-4 hover:underline\" to={{`/{self.plural}/${{row.original.id}}`}} "
                        f"state={{(table.options.meta as RowMeta).listState}}>{{{value}}}</Link>\n"
                        f"      {{row.original.deletedAtUtc && <Badge variant=\"secondary\">Deleted</Badge>}}\n    </span>\n  )")
                args = "{ row, table }"
            elif cell == "link":
                body, args = f"<LinkedName {self.link_target(field)} id={{{value}}} />", "{ row }"
            else:
                shown = self.shown(field, value)
                if cell == "badge":
                    shown = f"<Badge variant=\"outline\">{{{shown}}}</Badge>"
                elif cell == "date":
                    shown = f"<time dateTime={{{value}}}>{{{shown}}}</time>"
                elif cell == "money":
                    shown = f"<span className=\"block text-right tabular-nums\">{{{shown}}}</span>"
                else:
                    shown = f"<>{{{shown}}}</>"
                if field.get("optional") and cell != "yes-no":
                    shown = f"{value} === null ? null : {shown}"
                body, args = shown, "{ row }"
            blocks.append(f"{{\n  accessorKey: '{column}',\n  header: ({{ column }}) => (\n    {header}\n  ),\n"
                          f"  cell: ({args}) => {body},\n}},")
        return "\n".join(blocks)

    def filter_controls(self) -> str:
        controls = []
        for field in self.filters:
            column, label = _column(field), _words(field["name"])
            options = self.options(field)
            if field["kind"] == "link":
                controls.append(f"<LinkPicker {self.link_props(field)} emptyChoice={_attr(options[0])} className=\"w-full sm:w-44\" "
                                f"value={{query.{column}}} onChange={{(id) => setQuery({{ {column}: id }})}} />")
                continue
            if field["kind"] == "status":
                kind_type = _status_type(self.one, field)
                items = (f"  {{{_status_name(self.one, field)}.options.map((option) => <SelectItem key={{option}} value={{option}}>"
                         f"{{{_labels_const(field)}[option]}}</SelectItem>)}}")
            else:
                kind_type = "'yes' | 'no'"
                items = f"  <SelectItem value=\"yes\">{options[1]}</SelectItem>\n  <SelectItem value=\"no\">{options[2]}</SelectItem>"
            controls.append(
                f"<Select value={{query.{column} ?? 'all'}} onValueChange={{(value) => setQuery({{ {column}: value === 'all' ? undefined : value as {kind_type} }})}}>\n"
                f"  <SelectTrigger aria-label={_attr(label)} className=\"w-full sm:w-44\"><SelectValue /></SelectTrigger>\n"
                f"  <SelectContent>\n    <SelectItem value=\"all\">{options[0]}</SelectItem>\n  {items}\n  </SelectContent>\n</Select>")
        return "\n".join(controls)

    # The detail page.
    def detail_imports(self) -> str:
        util = self.util_imports([field for field in self.fields if self.kind(field, "cell") != "number"],
                                 {"formatDate", "formatDateTime"})
        shared = [_labels_const(field) for field in self.statuses] + (["numberText"] if self.number_helper() else [])
        lines = [util]
        if shared:
            lines.append(f"import {{ {', '.join(shared)} }} from './{self.plural}-page';")
        if self.links:
            lines.append("import { LinkedName } from './link-picker';")
        return "\n".join(lines)

    def heading_badge(self) -> str:
        if not self.statuses:
            return ""
        field = self.statuses[0]
        value = f"{self.item}.{_column(field)}"
        badge = f"<Badge variant=\"outline\">{{{self.shown(field, value)}}}</Badge>"
        return f"{{{value} !== null && {badge}}}" if field.get("optional") else badge

    def detail_fields(self) -> str:
        rows = []
        ordered = ([field for field in self.fields if field["kind"] != "long-text"]
                   + [field for field in self.fields if field["kind"] == "long-text"])
        for field in ordered:
            value, cell = f"{self.item}.{_column(field)}", self.kind(field, "cell")
            span = " className=\"sm:col-span-2\"" if cell == "long-text" else ""
            if cell == "link":
                shown = (f"<Link className=\"underline underline-offset-4\" to={{`/{field['target']}/${{{value}}}`}}>"
                         f"<LinkedName {self.link_target(field)} id={{{value}}} /></Link>")
            elif cell == "email":
                shown = f"<a className=\"break-all underline underline-offset-4\" href={{`mailto:${{{value}}}`}}>{{{value}}}</a>"
            elif cell in ("text", "long-text"):
                wrap = "whitespace-pre-wrap break-words" if cell == "long-text" else "break-words"
                shown = f"<span className=\"{wrap}\">{{{value}}}</span>"
            else:
                shown = self.shown(field, value)
            if field.get("optional") and cell != "yes-no":
                shown = f"{value} === null ? 'None' : {shown}"
            shown = shown if shown.startswith("<") else f"{{{shown}}}"
            rows.append(f"<Field label={_attr(_words(field['name']))}{span}>{shown}</Field>")
        return "\n".join(rows)

    # The form.
    def form_imports(self) -> str:
        names = [_status_name(self.one, field) for field in self.statuses] + [f"type {self.model}", f"type {self.model}Input"]
        lines = ["import { z } from 'zod';", self.contract_imports(*names)]
        inputs = {self.kind(field, "input") for field in self.fields}
        if "money" in inputs:
            lines.append("import { DEFAULT_CURRENCY, formatNumber } from '@app/shared-util';")
        if "textarea" in inputs:
            lines.append("import { Textarea } from '@app/shared-ui/components/ui/textarea';")
        if "checkbox" in inputs:
            lines.append("import { Checkbox } from '@app/shared-ui/components/ui/checkbox';")
        if "select" in inputs:
            lines.append("import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';")
        if "combobox" in inputs:
            lines.append("import { LinkPicker } from './link-picker';")
        return "\n".join(lines)

    def form_values(self) -> str:
        schema, values, inputs, helpers = [], [], [], set()
        for field in self.fields:
            column, kind, optional = _column(field), self.kind(field, "input"), bool(field.get("optional"))
            label = _words(field["name"]).lower()
            item = f"{self.item}?.{column}"
            required = "" if optional else f".min(1, {_js('Enter a name.' if field is self.name else 'Enter a ' + label + '.')})"
            if kind in ("input", "textarea", "email"):
                limit = {"input": 200, "textarea": 10000, "email": 254}[kind]
                rule = f"z.string().trim(){required}.max({limit}, {_js(f'Use {limit:,} characters or fewer.')})"
                if kind == "email":
                    rule += ".refine((value) => value === '' || z.email().safeParse(value).success, 'Enter a valid email address.')"
                value, data = f"{item} ?? ''", f"values.{column}"
            elif kind == "number":
                rule = f"z.string().trim(){required}.regex(/^(-?\\d{{1,15}}(\\.\\d{{1,4}})?)?$/, 'Enter a number.')"
                value, data = f"{item} ?? ''", f"values.{column}"
            elif kind == "money":
                helpers.add("money")
                rule = f"z.string().trim(){required}.regex(MONEY, 'Enter an amount, such as 1,250.00.')"
                value = f"{item} == null ? '' : formatNumber({item} / 100, 2)"
                # The schema needs an amount in a required box, so only an optional one gives undefined.
                data = f"toCents(values.{column})" + ("" if optional else " as number")
            elif kind == "date":
                helpers.add("date")
                rule = f"z.string().trim(){required}.refine((value) => value === '' || isRealDate(value), 'Enter a real date as YYYY-MM-DD.')"
                value, data = f"{item} ?? ''", f"values.{column}"
            elif kind == "checkbox":
                rule, value, data = "z.boolean()", f"{item} ?? false", f"values.{column}"
            elif kind == "select":
                rule = _status_name(self.one, field) + (".or(z.literal(''))" if optional else "")
                value = f"{item} ?? {_js('' if optional else field['options'][0])}"
                data = f"values.{column}"
            else:
                choose = f".min(1, {_js('Choose a ' + label + '.')})" if not optional else ""
                rule, value, data = f"z.string(){choose}", f"{item} ?? ''", f"values.{column}"
            if optional and kind != "checkbox":
                data = f"{data} || undefined" if kind != "money" else data
            schema.append(f"  {column}: {rule},")
            values.append(f"    {column}: {value},")
            inputs.append(f"    {column}: {data},")
        lines = []
        if "money" in helpers:
            lines += ["const MONEY = /^(-?(\\d{1,3}(,\\d{3})*|\\d+)(\\.\\d{1,2})?)?$/;", "",
                      "/** `1,250.50` is 125050 cents; an empty box is no amount. */",
                      "function toCents(text: string): number | undefined {",
                      "  if (text === '') return undefined;",
                      "  const [whole, fraction = ''] = text.replace(/[,-]/g, '').split('.');",
                      "  return (text.startsWith('-') ? -1 : 1) * (Number(whole) * 100 + Number(fraction.padEnd(2, '0')));",
                      "}", ""]
        if "date" in helpers:
            lines += ["function isRealDate(value: string): boolean {",
                      "  const date = new Date(`${value}T00:00:00.000Z`);",
                      "  return /^\\d{4}-\\d{2}-\\d{2}$/.test(value) && !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;",
                      "}", ""]
        lines += ["const formSchema = z.object({", *schema, "});", "type FormValues = z.infer<typeof formSchema>;", "",
                  f"function toValues({self.item}?: {self.model}): FormValues {{", "  return {", *values, "  };", "}", "",
                  f"function toInput(values: FormValues): {self.model}Input {{", "  return {", *inputs, "  };", "}"]
        return "\n".join(lines)

    def form_fields(self) -> str:
        items = []
        for field in self.fields:
            column, kind, label = _column(field), self.kind(field, "input"), _words(field["name"])
            wide = " className=\"sm:col-span-2\"" if kind in ("input", "textarea") else ""
            if kind == "checkbox":
                items.append(f"<FormField control={{form.control}} name=\"{column}\" render={{({{ field }}) => (\n"
                             f"  <FormItem className=\"flex flex-row flex-wrap items-center gap-2 self-end sm:col-span-2\">\n"
                             f"    <FormControl><Checkbox checked={{field.value}} onCheckedChange={{(checked) => field.onChange(checked === true)}} /></FormControl>\n"
                             f"    <FormLabel className=\"font-normal\">{label}</FormLabel>\n    <FormMessage />\n  </FormItem>\n)}} />")
                continue
            if kind == "select":
                options = "\n".join(f"        <SelectItem value={_attr(option)}>{_words(option)}</SelectItem>" for option in field["options"])
                control = (f"    <Select value={{field.value}} onValueChange={{field.onChange}}>\n"
                           f"      <FormControl><SelectTrigger aria-label={_attr(label)} className=\"w-full\"><SelectValue placeholder={_attr('Choose a ' + label.lower())} /></SelectTrigger></FormControl>\n"
                           f"      <SelectContent>\n{options}\n      </SelectContent>\n    </Select>")
            elif kind == "combobox":
                empty = " emptyChoice=\"None\"" if field.get("optional") else ""
                control = (f"    <FormControl><LinkPicker {self.link_props(field)}{empty} className=\"w-full\" value={{field.value || undefined}} "
                           f"onChange={{(id) => field.onChange(id ?? '')}} /></FormControl>")
            elif kind == "money":
                control = ("    <div className=\"flex\">\n"
                           "      <span className=\"inline-flex items-center rounded-l-md border border-r-0 border-input px-3 text-sm text-muted-foreground\">{DEFAULT_CURRENCY}</span>\n"
                           "      <FormControl><Input inputMode=\"decimal\" autoComplete=\"off\" className=\"rounded-l-none tabular-nums\" {...field} /></FormControl>\n"
                           "    </div>")
            else:
                props = {"input": 'autoComplete="off"', "email": 'inputMode="email" autoComplete="off"',
                         "number": 'inputMode="decimal" autoComplete="off"', "date": 'autoComplete="off" placeholder="YYYY-MM-DD"'}
                element = "Textarea" if kind == "textarea" else "Input"
                control = f"    <FormControl><{element} {props.get(kind, '')} {{...field}} /></FormControl>".replace("  {", " {")
            items.append(f"<FormField control={{form.control}} name=\"{column}\" render={{({{ field }}) => (\n"
                         f"  <FormItem{wide}>\n    <FormLabel>{label}</FormLabel>\n{control}\n    <FormMessage />\n  </FormItem>\n)}} />")
        body = "\n".join("  " + line if line else "" for line in "\n".join(items).splitlines())
        return f"<div className=\"grid gap-4 sm:grid-cols-2\">\n{body}\n</div>"

    # The hooks and their test.
    def link_hooks(self) -> str:
        if not self.links:
            return ""
        return """/** An item of another feature that a link field points at. */
export type LinkedItem = { id: string; name: string };
type LinkedRecord = Record<string, unknown> & { id: string };

/** The first page of another feature's items that match the search, for a link field's Select. */
export function useLinkedItems(path: string, nameField: string, search: string) {
  return useQuery({
    queryKey: [path, 'link-choices', search] as const,
    queryFn: async () => {
      const page = await apiRequest<{ items: LinkedRecord[] }>(`/${path}?${new URLSearchParams(search ? { search } : {}).toString()}`);
      return page.items.map((item): LinkedItem => ({ id: item.id, name: String(item[nameField]) }));
    },
    placeholderData: keepPreviousData,
  });
}

/** One linked item's name, for a link field's cell, detail row and chosen value. */
export function useLinkedItem(path: string, nameField: string, id: string | null) {
  return useQuery({
    queryKey: [path, 'link-name', id] as const,
    queryFn: async (): Promise<LinkedItem> => {
      const item = await apiRequest<LinkedRecord>(`/${path}/${encodeURIComponent(id ?? '')}`);
      return { id: item.id, name: String(item[nameField]) };
    },
    enabled: Boolean(id),
  });
}"""

    def test_fields(self) -> str:
        return "\n".join(f"{_column(field)}: {_js(_sample(field, self.full_kinds))}"
                         f"{' as const' if field['kind'] == 'status' else ''}," for field in self.fields)

    def test_input(self) -> str:
        sample = {_column(field): _sample(field, self.full_kinds) for field in self.fields}
        name = _column(self.name)
        sample[name] = "Migration review"
        values = ", ".join(f"{column}: {_js(value)}{' as const' if column in {_column(f) for f in self.statuses} else ''}"
                           for column, value in sample.items())
        query = {"search": "migration"}
        for field in self.filters:
            query[_column(field)] = "yes" if field["kind"] == "yes-no" else _sample(field, self.full_kinds)
        query_text = ", ".join(f"{key}: {_js(value)}{' as const' if key != 'search' else ''}" for key, value in query.items())
        parameters = "&".join(f"{key}={value}" for key, value in query.items())
        return "\n".join([
            f"const input = {{ {values} }};",
            f"const changed = {{ ...input, {name}: 'Updated review' }};",
            f"const listQuery = {{ {query_text}, sortBy: {_js(name)} as const }};",
            f"const listPath = '/api/v1/{self.plural}?{parameters}&sortBy={name}&sortOrder=asc&after=cursor-1';",
        ])

    # The browser flows.
    def flow_fields(self) -> str:
        name, name_label = _column(self.name), _words(self.name["name"])
        data, fills, shown = {}, [], []
        for field in self.fields:
            if field is self.name or field["kind"] == "link":
                continue
            column, label, kind = _column(field), _words(field["name"]), self.kind(field, "input")
            value = data[column] = _sample(field, self.full_kinds)
            box = f"dialog.getByLabel({_js(label)}, {{ exact: true }})"
            if kind == "select":
                fills += [f"await dialog.getByRole('combobox', {{ name: {_js(label)} }}).click();",
                          f"await page.getByRole('option', {{ name: {_js(_words(value))}, exact: true }}).click();"]
                shown.append(_js(label + _words(value)))
            elif kind == "checkbox":
                fills.append(f"await {box}.{'check' if value else 'uncheck'}();")
                shown.append(_js(label + ("Yes" if value else "No")))
            elif kind == "money":
                # The sample in cents is what the person types as an amount.
                fills.append(f"await {box}.fill('1,250.00');")
                shown.append(f"/{re.escape(label)}[A-Z]{{3}} 1,250\\.00/")
                data[column] = 125000
            elif kind == "number":
                fills.append(f"await {box}.fill('42.5');")
                shown.append(_js(label + "42.5"))
            else:
                fills.append(f"await {box}.fill({_js(value)});")
                shown.append(_js(label + str(value)))
        # With no other field to fill, the function still checks the dialog it got.
        fills = fills or ["await expect(dialog.getByLabel(NAME, { exact: true })).not.toHaveValue('');"]
        values = ", ".join([f"{name}: name"] + [f"{column}: {_js(value)}" for column, value in data.items()])
        lines = [
            f"const NAME = {_js(name_label)};", f"const NAME_KEY = {_js(name)};", "",
            f"/** A {self.one.replace('-', ' ')} the API accepts, with this name. */",
            f"function {self.item}Data(name: string): Record<string, unknown> {{", f"  return {{ {values} }};", "}", "",
            "/** Fills the form's fields other than the name; the Details card then shows each SHOWN text. */",
            f"async function fill{self.model}Form(page: Page, dialog: Locator) {{", *("  " + line for line in fills), "}",
            f"const SHOWN: (string | RegExp)[] = [{', '.join(shown)}];", "",
            "/** The list filter that a reloaded link keeps, and the values that leave an item out of it. */",
            "type ListFilter = { choose(page: Page): Promise<void>; expectChosen(page: Page): Promise<void>; "
            "address: RegExp; exportQuery: string; leftOut: Record<string, unknown> };",
        ]
        chosen = next((field for field in self.filters if field["kind"] in ("status", "yes-no")), None)
        if chosen is None:
            lines.append("const LIST_FILTER = null as ListFilter | null;")
        else:
            column, label, sample = _column(chosen), _words(chosen["name"]), _sample(chosen, self.full_kinds)
            if chosen["kind"] == "status":
                option, parameter, left_out = _words(sample), sample, _sample(chosen, self.full_kinds, changed=True)
            else:
                option, parameter, left_out = self.options(chosen)[1 if sample else 2], "yes" if sample else "no", not sample
            lines += [
                "const LIST_FILTER = {", "  async choose(page) {",
                f"    await page.getByRole('combobox', {{ name: {_js(label)} }}).click();",
                f"    await page.getByRole('option', {{ name: {_js(option)}, exact: true }}).click();",
                "  },", "  async expectChosen(page) {",
                f"    await expect(page.getByRole('combobox', {{ name: {_js(label)} }})).toHaveText({_js(option)});",
                "  },", f"  address: /{column}={parameter}/,", f"  exportQuery: '&{column}={parameter}',",
                f"  leftOut: {{ {column}: {_js(left_out)} }},", "} as ListFilter | null;"]
        lines += ["", "/** Four changes after the create, and the text of the oldest two of the five entries shown. */",
                  "const CHANGES = [" + ", ".join(f"{{ {name}: {_js(value)} }}" for value in ("Website relaunch", "Second", "Third", "Fourth")) + "];",
                  f"const OLDEST_SHOWN = [/^{re.escape(name_label)} changed from Website redesign to Website relaunch/, /^Created the {self.one.replace('-', ' ')}/];"]
        return "\n".join(lines)

    def bodies(self) -> dict[str, str]:
        return {
            "link-hooks": self.link_hooks(), "list-imports": self.list_imports(), "list-fields": self.list_fields(),
            "read-filters": self.read_filters(), "columns": self.columns_body(), "filter-controls": self.filter_controls(),
            "detail-imports": self.detail_imports(), "heading-badge": self.heading_badge(),
            "detail-fields": self.detail_fields(), "form-imports": self.form_imports(), "form-values": self.form_values(),
            "form-fields": self.form_fields(), "test-fields": self.test_fields(), "test-input": self.test_input(),
            "flow-fields": self.flow_fields(),
        }


def render_feature_web(fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any],
                       link_names: dict[str, str]) -> dict[str, str]:
    """Return the renamed web library, its hooks test and its browser flows."""
    bodies = _Web(fields, one, plural, kinds, link_names).bodies()
    name = _column(next(field for field in fields if field["kind"] == "text" and not field.get("optional")))
    files = {}
    for path in WEB_FILES:
        text = _rename((STARTER / path).read_text(encoding="utf-8"), one, plural)
        for match in list(MARK.finditer(text)):
            text = _replace_mark(text, match["name"], bodies[match["name"]])
        if name != "name":
            text = re.sub(rf"\b({_camel(one)}(?:\.data\?)?)\.name\b", rf"\1.{name}", text)
            text = text.replace("{ id: string; name: string }[]", f"{{ id: string; {name}: string }}[]")
        target = re.sub(r"projects|project", lambda match: plural if match[0] == "projects" else one, path)
        files[target] = text
    if any(field["kind"] == "link" for field in fields):
        files[f"libs/{plural}/web/src/pages/link-picker.tsx"] = LINK_PICKER.read_text(encoding="utf-8").replace("@@PLURAL@@", plural)
    return files
