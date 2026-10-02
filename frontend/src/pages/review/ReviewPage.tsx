import { useParams } from "react-router-dom";

export function ReviewPage() {
  const { matchId } = useParams();
  return <h1>{`Review ${matchId}`}</h1>;
}
