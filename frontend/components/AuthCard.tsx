"use client";

import {useState} from "react";

interface AuthCardProps {
    apiBase: string;
    onAuthSuccess: (token: string) => void;
}

export default function AuthCard({apiBase, onAuthSuccess}: AuthCardProps) {
    // Navigation & Step State
    const [isSignup, setIsSignup] = useState(false);
    const [step, setStep] = useState<"FORM" | "OTP">("FORM");

    // Form Field States
    const [authEmail, setAuthEmail] = useState("");
    const [authPassword, setAuthPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [otpCode, setOtpCode] = useState("");

    // UI Feedback States
    const [authError, setAuthError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    // Normalize apiBase to avoid double slashes
    const cleanApiBase = apiBase.replace(/\/$/, "");

    // Step 1: Submit Login or Signup
    const handleAuthSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setAuthError(null);
        setSuccessMessage(null);

        // Front-end validation for Signup
        if (isSignup) {
            if (authPassword !== confirmPassword) {
                setAuthError("Passwords do not match.");
                return;
            }

            const hasMinLength = authPassword.length >= 8;
            const hasLetter = /[a-zA-Z]/.test(authPassword);
            const hasNumber = /[0-9]/.test(authPassword);

            if (!hasMinLength || !hasLetter || !hasNumber) {
                setAuthError(
                    "Password must be at least 8 characters long and include both letters and numbers."
                );
                return;
            }
        }

        setIsLoading(true);

        const endpoint = isSignup ? "/api/auth/signup" : "/api/auth/login";
        let headers: Record<string, string> = {};
        let body: any;

        if (isSignup) {
            headers["Content-Type"] = "application/json";
            body = JSON.stringify({email: authEmail, password: authPassword});
        } else {
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            const formData = new URLSearchParams();
            formData.append("username", authEmail);
            formData.append("password", authPassword);
            body = formData.toString();
        }

        try {
            const res = await fetch(`${cleanApiBase}${endpoint}`, {
                method: "POST",
                headers,
                body,
            });

            const contentType = res.headers.get("content-type");
            let data: any = {};
            if (contentType && contentType.includes("application/json")) {
                data = await res.json();
            }

            if (!res.ok) {
                // If unverified user tries to log in, prompt them for OTP
                if (res.status === 403 && data.detail?.includes("not verified")) {
                    setStep("OTP");
                    throw new Error("Account not verified. We sent a code to your email.");
                }
                throw new Error(data.detail || `Server error (${res.status})`);
            }

            if (isSignup) {
                setSuccessMessage(`Verification code sent to ${authEmail}`);
                setStep("OTP");
            } else {
                if (!data.access_token) {
                    throw new Error("No access token returned from server.");
                }
                localStorage.setItem("token", data.access_token);
                onAuthSuccess(data.access_token);
            }
        } catch (err: any) {
            setAuthError(err.message || "An error occurred during authentication.");
        } finally {
            setIsLoading(false);
        }
    };

    // Step 2: Submit OTP Verification Code
    const handleOtpSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setAuthError(null);
        setSuccessMessage(null);

        if (otpCode.length !== 6) {
            setAuthError("Verification code must be 6 digits.");
            return;
        }

        setIsLoading(true);

        try {
            const res = await fetch(`${cleanApiBase}/api/auth/verify-otp`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({email: authEmail, code: otpCode}),
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                throw new Error(data.detail || "Verification failed.");
            }

            setSuccessMessage("Email verified successfully! Please log in.");
            setStep("FORM");
            setIsSignup(false);
            setAuthPassword("");
            setConfirmPassword("");
            setOtpCode("");
        } catch (err: any) {
            setAuthError(err.message || "An error occurred during verification.");
        } finally {
            setIsLoading(false);
        }
    };

    // Resend OTP Code
    const handleResendOtp = async () => {
        setAuthError(null);
        setSuccessMessage(null);
        setIsLoading(true);

        try {
            const res = await fetch(`${cleanApiBase}/api/auth/resend-otp`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({email: authEmail}),
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                throw new Error(data.detail || "Failed to resend code.");
            }

            setSuccessMessage("A new 6-digit code has been sent to your email.");
        } catch (err: any) {
            setAuthError(err.message || "Failed to resend verification code.");
        } finally {
            setIsLoading(false);
        }
    };

    const toggleMode = () => {
        setIsSignup(!isSignup);
        setStep("FORM");
        setAuthError(null);
        setSuccessMessage(null);
        setConfirmPassword("");
        setOtpCode("");
    };

    return (
        <main className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-4">
            <div
                className="w-full max-w-md bg-slate-800/90 border border-slate-700 rounded-2xl p-8 space-y-6 shadow-2xl">
                <div className="text-center space-y-2">
                    <h1 className="text-3xl font-extrabold tracking-tight text-emerald-400">
                        🇸🇬 One Day Out Planner
                    </h1>
                    <p className="text-slate-400 text-sm">
                        {step === "OTP"
                            ? "Enter 6-digit verification code"
                            : isSignup
                                ? "Create an account to start planning"
                                : "Log in to access your itinerary engine"}
                    </p>
                </div>

                {authError && (
                    <div className="p-3 bg-red-900/40 border border-red-700 rounded-xl text-red-200 text-xs text-left">
                        ⚠️ {authError}
                    </div>
                )}

                {successMessage && (
                    <div
                        className="p-3 bg-emerald-900/40 border border-emerald-700 rounded-xl text-emerald-200 text-xs text-left">
                        ✅ {successMessage}
                    </div>
                )}

                {/* STEP 1: FORM VIEW */}
                {step === "FORM" && (
                    <form onSubmit={handleAuthSubmit} autoComplete="off" className="space-y-4">
                        <div className="space-y-1.5 text-left">
                            <label className="text-xs font-semibold text-slate-400">
                                Email Address
                            </label>
                            <input
                                type="email"
                                required
                                disabled={isLoading}
                                autoComplete={isSignup ? "off" : "email"}
                                value={authEmail}
                                onChange={(e) => setAuthEmail(e.target.value)}
                                placeholder="you@example.com"
                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
                            />
                        </div>

                        <div className="space-y-1.5 text-left">
                            <label className="text-xs font-semibold text-slate-400">
                                Password
                            </label>
                            <input
                                type="password"
                                required
                                disabled={isLoading}
                                autoComplete={isSignup ? "new-password" : "current-password"}
                                value={authPassword}
                                onChange={(e) => setAuthPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
                            />
                            {isSignup && (
                                <p className="text-[12px] text-slate-400 pt-0.5">
                                    Must be at least 8 characters with letters & numbers.
                                </p>
                            )}
                        </div>

                        {/* Confirm Password Field (Signup only) */}
                        {isSignup && (
                            <div className="space-y-1.5 text-left">
                                <label className="text-xs font-semibold text-slate-400">
                                    Confirm Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    disabled={isLoading}
                                    autoComplete="new-password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
                                />
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-800 font-bold text-slate-950 disabled:text-slate-400 py-3 rounded-xl transition-all text-sm cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-emerald-500/10"
                        >
                            {isLoading ? "Connecting..." : isSignup ? "Sign Up" : "Log In"}
                        </button>
                    </form>
                )}

                {/* STEP 2: OTP VIEW */}
                {step === "OTP" && (
                    <form onSubmit={handleOtpSubmit} className="space-y-4">
                        <div className="space-y-1.5 text-left">
                            <label className="text-xs font-semibold text-slate-400">
                                Code sent to{" "}
                                <span className="text-white font-medium">{authEmail}</span>
                            </label>
                            <input
                                type="text"
                                required
                                maxLength={6}
                                disabled={isLoading}
                                value={otpCode}
                                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                                placeholder="123456"
                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-3 text-center text-2xl tracking-[8px] font-mono text-emerald-400 focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-800 font-bold text-slate-950 disabled:text-slate-400 py-3 rounded-xl transition-all text-sm cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-emerald-500/10"
                        >
                            {isLoading ? "Verifying..." : "Verify Code"}
                        </button>

                        <div className="flex items-center justify-between pt-2 text-xs">
                            <button
                                type="button"
                                disabled={isLoading}
                                onClick={handleResendOtp}
                                className="text-emerald-400 hover:underline cursor-pointer disabled:opacity-50 font-medium"
                            >
                                Resend Code
                            </button>
                            <button
                                type="button"
                                disabled={isLoading}
                                onClick={() => {
                                    setStep("FORM");
                                    setAuthError(null);
                                }}
                                className="text-slate-400 hover:text-white cursor-pointer disabled:opacity-50"
                            >
                                ← Back
                            </button>
                        </div>
                    </form>
                )}

                {step === "FORM" && (
                    <div className="text-center pt-2">
                        <button
                            type="button"
                            disabled={isLoading}
                            onClick={toggleMode}
                            className="text-sm font-semibold text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer disabled:opacity-50"
                        >
                            {isSignup
                                ? "Already have an account? Log in"
                                : "Need an account? Sign up"}
                        </button>
                    </div>
                )}
            </div>
        </main>
    );
}