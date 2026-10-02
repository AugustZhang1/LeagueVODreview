import { useEffect } from "react";
import { describeError, type ErrorContext } from "../lib/errors";
import { Button } from "./Button";
import styles from "./ErrorBox.module.css";

type Props = { error: unknown; onRetry?: () => void; context?: ErrorContext };

export function ErrorBox({ error, onRetry, context }: Props) {
  const { message, canRetry } = describeError(error, context);
  useEffect(() => {
    if (canRetry) console.error(error);
  }, [canRetry, error]);
  return (
    <div role="alert" className={styles.box}>
      <p className={styles.message}>{message}</p>
      {canRetry && onRetry && <Button onClick={onRetry}>Retry</Button>}
    </div>
  );
}
