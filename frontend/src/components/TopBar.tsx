import { NavLink, Link } from "react-router-dom";
import styles from "./TopBar.module.css";

export function TopBar() {
  return (
    <header className={styles.bar}>
      <div className={styles.inner}>
        <Link to="/" className={styles.wordmark}>
          LeagueVODreview
        </Link>
        <nav className={styles.nav} aria-label="Main">
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? styles.active : styles.link)}
          >
            Search
          </NavLink>
          <NavLink
            to="/model"
            className={({ isActive }) => (isActive ? styles.active : styles.link)}
          >
            Model
          </NavLink>
        </nav>
      </div>
    </header>
  );
}
