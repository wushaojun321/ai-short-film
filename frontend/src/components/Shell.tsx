import { useLocation } from "react-router-dom";
import Nav from "./Nav";

interface ShellProps {
  children: React.ReactNode;
}

export default function Shell({ children }: ShellProps) {
  const location = useLocation();
  const isHome = location.pathname === "/projects" || location.pathname === "/";

  return (
    <div className="app-workspace">
      <Nav />
      <main className={`pt-14 ${isHome ? "" : ""}`}>
        {children}
      </main>
    </div>
  );
}
