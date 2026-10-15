import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Cockpit" },
  { to: "/agenten", label: "Agenten" },
  { to: "/ziele", label: "Ziele & Fortschritt" },
  { to: "/kategorien", label: "Kategorien" },
  { to: "/dokumente", label: "Dokumente" },
  { to: "/integrationen", label: "Integrationen" },
];

export default function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="brand">Nauteron</div>
      <div className="brand-claim">Know the course. Act with clarity.</div>
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.to === "/"}
          className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}
