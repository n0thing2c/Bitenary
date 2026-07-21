import { redirectToLogin, redirectToSignup } from "../api/authApi";

import "./LoginCard.css";

export function LoginCard() {
  return (
    <section className="login-card" aria-labelledby="login-title">
      <h1 id="login-title" className="login-card__title">
        Login
      </h1>

      <button className="login-card__button" type="button" onClick={redirectToLogin}>
        Log in
      </button>

      <p className="login-card__signup">
        Don&apos;t have an account?{" "}
        <button
          className="login-card__link"
          type="button"
          onClick={redirectToSignup}
        >
          Sign up
        </button>
      </p>
    </section>
  );
}
