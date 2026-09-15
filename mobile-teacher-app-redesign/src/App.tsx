/* Точка входа: hash-роутинг, таб-навигация, центрированная колонка
   (приложение проектируется под смартфон; на десктопе — колонка 480px). */

import { useRoute } from "./lib/router";
import { ToastProvider } from "./components/ui";
import { BottomNav } from "./components/shell";
import TodayScreen from "./screens/Today";
import GroupsScreen from "./screens/Groups";
import GroupDetailScreen from "./screens/GroupDetail";
import StatementScreen from "./screens/Statement";
import ScheduleScreen from "./screens/Schedule";
import LessonRunScreen from "./screens/LessonRun";
import AnalyticsScreen from "./screens/Analytics";
import SettingsScreen from "./screens/Settings";

function RouterView({ seg }: { seg: string[] }) {
  const [root, a, b] = seg;
  const key = seg.join("/") || "today";

  let view: React.ReactNode;
  switch (root) {
    case "groups":
      view = <GroupsScreen />;
      break;
    case "group":
      view = <GroupDetailScreen id={Number(a)} />;
      break;
    case "statement":
      view = <StatementScreen groupId={Number(a)} subjectId={Number(b)} />;
      break;
    case "schedule":
      view = <ScheduleScreen />;
      break;
    case "lesson":
      view = <LessonRunScreen id={Number(a)} />;
      break;
    case "analytics":
      view = <AnalyticsScreen />;
      break;
    case "more":
      view = <SettingsScreen />;
      break;
    case "today":
    default:
      view = <TodayScreen />;
      break;
  }

  return (
    <div key={key} className="an-rise z-50">
      {view}
    </div>
  );
}

export default function App() {
  const seg = useRoute();
  const root = seg[0] ?? "today";
  // На экране занятия таб-бар скрыт: там свои компактные шапка и подвал.
  const showNav = root !== "lesson";

  return (
    <ToastProvider>
      <div className="mx-auto w-full max-w-[480px] min-h-screen border-x border-line bg-bg">
        <RouterView seg={seg} />
        {showNav && <BottomNav segment={root} />}
      </div>
    </ToastProvider>
  );
}
