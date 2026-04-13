import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/app/portal", label: "绑定" },
  { to: "/app/schedule", label: "课表" },
  { to: "/app/grades", label: "成绩" },
  { to: "/app/settings", label: "设置" }
];

export function AppShell() {
  return (
    <div className="shell">
      <main className="app-main">
        <Outlet />
      </main>
      <nav className="bottom-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
