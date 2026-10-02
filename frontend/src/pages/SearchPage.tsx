import styles from "./SearchPage.module.css";

export function SearchPage() {
  return (
    <div className={styles.page}>
      <h1 className={styles.wordmark}>LeagueVODreview</h1>
      <p className={styles.tagline}>
        Grades every moment of your ranked games by how much it moved your team's chance to win.
      </p>
    </div>
  );
}
