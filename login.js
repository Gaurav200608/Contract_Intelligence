const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const loginButton = document.getElementById("loginButton");
const loginButtonLabel = loginButton.querySelector(".login-button-label");
const loginSpinner = loginButton.querySelector(".login-button-spinner");
const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");

let csrfToken = "";

function showLoginError(message) {
    loginError.textContent = message;
    loginError.hidden = false;
}

function setSubmitting(submitting) {
    loginButton.disabled = submitting;
    loginSpinner.hidden = !submitting;
    loginButtonLabel.textContent = submitting ? "Signing in..." : "Sign in";
}

async function initializeLogin() {
    const statusResponse = await fetch("/api/auth/status", {
        credentials: "same-origin",
        cache: "no-store"
    });
    const status = await statusResponse.json();
    if (status.authenticated) {
        window.location.replace("/dashboard");
        return;
    }

    const csrfResponse = await fetch("/api/auth/csrf", {
        credentials: "same-origin",
        cache: "no-store"
    });
    if (!csrfResponse.ok) {
        throw new Error("Could not initialize a secure sign-in request. Refresh the page and try again.");
    }
    csrfToken = (await csrfResponse.json()).csrf_token;

    const query = new URLSearchParams(window.location.search);
    if (query.get("expired") === "1") {
        showLoginError("Your session expired. Please sign in again.");
    } else if (query.has("next") && query.get("next") !== "/dashboard") {
        showLoginError("Sign in to continue to your workspace.");
    }
}

togglePassword.addEventListener("click", () => {
    const reveal = passwordInput.type === "password";
    passwordInput.type = reveal ? "text" : "password";
    togglePassword.textContent = reveal ? "Hide" : "Show";
    togglePassword.setAttribute("aria-pressed", String(reveal));
    passwordInput.focus();
});

loginForm.addEventListener("submit", async event => {
    event.preventDefault();
    loginError.hidden = true;

    const username = document.getElementById("username").value.trim();
    const password = passwordInput.value;
    if (!username || !password) {
        showLoginError("Enter your username or email and password.");
        return;
    }

    setSubmitting(true);
    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken
            },
            body: JSON.stringify({
                username,
                password,
                remember_me: document.getElementById("rememberMe").checked
            })
        });
        const result = await response.json();
        if (!response.ok) {
            showLoginError(result.detail || "Sign-in failed. Please try again.");
            return;
        }
        window.location.replace("/dashboard");
    } catch {
        showLoginError("Unable to reach the sign-in service. Check that the application is running.");
    } finally {
        setSubmitting(false);
    }
});

initializeLogin().catch(() => {
    showLoginError("Could not initialize sign-in. Refresh the page or check the application service.");
});
