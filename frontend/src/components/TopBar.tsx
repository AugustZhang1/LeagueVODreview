import { TrendingUp } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { addRecent, parseRiotId, readPlatform } from "../pages/search/storage";
import styles from "./TopBar.module.css";

const navClass = ({ isActive }: { isActive: boolean }) => (isActive ? styles.active : styles.link);

export function TopBar() {
  const { pathname } = useLocation();
  return (
    <header className={styles.bar}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand}>
          <span className={styles.mark}>
            <TrendingUp size={14} aria-hidden="true" />
          </span>
          LeagueVODreview
        </Link>
        <nav className={styles.nav} aria-label="Main">
          <NavLink to="/" end className={navClass}>
            Search
          </NavLink>
          <NavLink to="/model" className={navClass}>
            Model
          </NavLink>
        </nav>
        {/* The home page has its own, bigger, search. */}
        {pathname !== "/" && <RiotIdSearch />}
      </div>
    </header>
  );
}

/** Riot ID search for the pages without one. Pressing "/" focuses it. */
function RiotIdSearch() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      // Typing a "/" into another field stays a "/".
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }
      e.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    const parsed = parseRiotId(value);
    // Invalid input does nothing; the field keeps focus.
    if ("error" in parsed) return;
    const platform = readPlatform();
    addRecent({ platform, ...parsed });
    navigate(`/p/${platform}/${encodeURIComponent(parsed.name)}/${encodeURIComponent(parsed.tag)}`);
    setValue("");
  }

  return (
    <form className={styles.search} role="search" onSubmit={submit}>
      <input
        ref={inputRef}
        className={styles.input}
        type="text"
        aria-label="Riot ID"
        placeholder="Search a Riot ID"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
      <kbd className={styles.key} aria-hidden="true">
        /
      </kbd>
    </form>
  );
}
