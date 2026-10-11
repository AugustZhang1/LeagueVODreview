import { useState } from "react";
import { Button } from "../../components/Button";
import { Panel } from "../../components/Panel";
import { formatTime } from "../../lib/format";
import styles from "./GameNotes.module.css";

const storageKey = (matchId: string, participantId: number) =>
  `lolreview:notes:${matchId}:${participantId}`;

function loadNotes(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function saveNotes(key: string, text: string) {
  try {
    localStorage.setItem(key, text);
  } catch {
    // storage unavailable (private mode): the notes last only for this visit
  }
}

/** Notes on one game, kept in this browser for this player's review. */
export function GameNotes({
  matchId,
  participantId,
  t,
}: {
  matchId: string;
  participantId: number;
  t: number;
}) {
  const key = storageKey(matchId, participantId);
  const [text, setText] = useState(() => loadNotes(key));
  const change = (next: string) => {
    setText(next);
    saveNotes(key, next);
  };
  const addTime = () => {
    const sep = text === "" || text.endsWith("\n") ? "" : "\n";
    change(`${text}${sep}${formatTime(t)} `);
  };
  return (
    <Panel title="Notes" actions={<Button onClick={addTime}>Add time</Button>}>
      <textarea
        aria-label="Your notes on this game"
        className={styles.text}
        value={text}
        onChange={(e) => change(e.target.value)}
      />
    </Panel>
  );
}
