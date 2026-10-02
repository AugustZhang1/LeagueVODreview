import { useParams } from "react-router-dom";

export function GamesPage() {
  const { name, tag } = useParams();
  return <h1>{`${name}#${tag}`}</h1>;
}
