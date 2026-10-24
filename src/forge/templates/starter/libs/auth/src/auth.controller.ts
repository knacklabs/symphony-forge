import { Body, Controller, Get, HttpCode, Post, Req, Res } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ApiCookieAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import type { Request, Response } from 'express';
import { ApiEnvelope, ApiErrors, ApiZodBody, Public, ZodValidationPipe } from '@app/core';
import { CurrentAccount, type AccountPrincipal } from '@app/core';
import { sessionOptions } from './session.guard';
import { AuthService, type SessionCookies } from './auth.service';
import { AccountResponseDto, MessageResponseDto } from './auth.dto';
import { forgotPasswordSchema, resetPasswordSchema, signInSchema, signUpSchema, type AuthCredentials, type ForgotPasswordInput, type ResetPasswordInput } from '@app/shared';

@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService, private readonly config: ConfigService) {}

  @Public()
  @Post('sign-up')
  @Throttle({ default: { limit: 30, ttl: 60_000 } })
  @ApiZodBody(signUpSchema)
  @ApiOperation({ summary: 'Create an account and start a session.' })
  @ApiEnvelope(AccountResponseDto, 201)
  @ApiErrors(400, 409, 429)
  async signUp(
    @Body(new ZodValidationPipe(signUpSchema)) input: AuthCredentials,
    @Res({ passthrough: true }) response: Response,
  ): Promise<AccountResponseDto> {
    const result = await this.auth.signUp(input.email, input.password);
    this.setSessionCookies(response, result.cookies);
    return result.account;
  }

  @Public()
  @Post('sign-in')
  @HttpCode(200)
  @Throttle({ default: { limit: 30, ttl: 60_000 } })
  @ApiZodBody(signInSchema)
  @ApiOperation({ summary: 'Sign in and start a server session.' })
  @ApiEnvelope(AccountResponseDto, 200)
  @ApiErrors(400, 401, 429)
  async signIn(
    @Body(new ZodValidationPipe(signInSchema)) input: AuthCredentials,
    @Res({ passthrough: true }) response: Response,
  ): Promise<AccountResponseDto> {
    const result = await this.auth.signIn(input.email, input.password);
    this.setSessionCookies(response, result.cookies);
    return result.account;
  }

  @Get('me')
  @ApiCookieAuth('session')
  @ApiOperation({ summary: 'Read the signed-in account.' })
  @ApiEnvelope(AccountResponseDto, 200)
  @ApiErrors(401)
  currentAccount(@CurrentAccount() account: AccountPrincipal): AccountResponseDto {
    return { id: account.id, email: account.email, role: account.role };
  }

  @Post('sign-out')
  @HttpCode(200)
  @ApiCookieAuth('session')
  @ApiOperation({ summary: 'End the current server session.' })
  @ApiEnvelope(MessageResponseDto, 200)
  @ApiErrors(401, 403)
  async signOut(
    @CurrentAccount() account: AccountPrincipal,
    @Req() request: Request,
    @Res({ passthrough: true }) response: Response,
  ): Promise<{ message: string }> {
    const token = request.cookies?.starter_session as string | undefined;
    await this.auth.signOut(account.id, token);
    const secure = this.config.getOrThrow<string>('APP_ENV') !== 'development' && this.config.getOrThrow<string>('APP_ENV') !== 'test';
    response.clearCookie('starter_session', { httpOnly: true, sameSite: 'lax', secure, path: '/' });
    response.clearCookie('starter_csrf', { httpOnly: false, sameSite: 'lax', secure, path: '/' });
    return { message: 'You have signed out.' };
  }

  @Public()
  @Post('forgot-password')
  @HttpCode(200)
  @Throttle({ default: { limit: 30, ttl: 60_000 } })
  @ApiZodBody(forgotPasswordSchema)
  @ApiOperation({ summary: 'Request a password reset link.' })
  @ApiEnvelope(MessageResponseDto, 200)
  @ApiErrors(400, 429)
  forgotPassword(@Body(new ZodValidationPipe(forgotPasswordSchema)) input: ForgotPasswordInput): Promise<{ message: string }> {
    return this.auth.forgotPassword(input.email);
  }

  @Public()
  @Post('reset-password')
  @HttpCode(200)
  @Throttle({ default: { limit: 30, ttl: 60_000 } })
  @ApiZodBody(resetPasswordSchema)
  @ApiOperation({ summary: 'Set a new password with a single-use reset link.' })
  @ApiEnvelope(MessageResponseDto, 200)
  @ApiErrors(400, 429)
  resetPassword(@Body(new ZodValidationPipe(resetPasswordSchema)) input: ResetPasswordInput): Promise<{ message: string }> {
    return this.auth.resetPassword(input.token, input.password);
  }

  private setSessionCookies(response: Response, session: SessionCookies): void {
    const environment = this.config.getOrThrow<string>('APP_ENV');
    response.cookie('starter_session', session.sessionToken, sessionOptions(environment, session.expiresAtUtc));
    response.cookie('starter_csrf', session.csrfToken, {
      ...sessionOptions(environment, session.expiresAtUtc),
      httpOnly: false,
    });
  }
}
