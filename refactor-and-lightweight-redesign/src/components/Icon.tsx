import type { CSSProperties } from "react";
export type IconName =
  | "home"
  | "users"
  | "book"
  | "calendar"
  | "chart"
  | "settings"
  | "help"
  | "arrow"
  | "left"
  | "right"
  | "plus"
  | "clock"
  | "check"
  | "download"
  | "bell"
  | "search"
  | "close"
  | "menu"
  | "chevron"
  | "file"
  | "shield"
  | "logout"
  | "more"
  | "play"
  | "leaf";
const paths: Record<IconName, React.ReactNode> = {
  home: (
    <>
      <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M21 21v-2a4 4 0 0 0-3-3.87" />
      <circle cx="9.5" cy="7" r="4" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  book: (
    <>
      <path d="M12 5v16M12 5C9 2 4 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-2-1-7-2-10 1Z" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2M8 18h2" />
    </>
  ),
  chart: (
    <>
      <path d="M4 3v18h17M9 16v-5M14 16V7M19 16v-8" />
    </>
  ),
  settings: (
    <>
      <path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 8.5a2.5 2.5 0 1 1 4 2c-1.5 1-1.5 1.5-1.5 2.5M12 17h.01" />
    </>
  ),
  arrow: <path d="M4 12h15m-5-5 5 5-5 5" />,
  left: <path d="m14 6-6 6 6 6" />,
  right: <path d="m9 6 6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  close: <path d="m6 6 12 12M6 18 18 6" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  chevron: <path d="m7 10 5 5 5-5" />,
  file: (
    <>
      <path d="M14 2H5v20h14V7ZM14 2v6h5M8 12h8M8 16h6" />
    </>
  ),
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  logout: <path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4" />,
  more: (
    <>
      <circle cx="5" cy="12" r="1" />
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
    </>
  ),
  play: <path d="m8 4 12 8-12 8Z" />,
  leaf: (
    <>
      <path d="M19 3S3 3 3 13a7 7 0 0 0 12 5c4-4 4-15 4-15ZM5 20 15 9" />
    </>
  ),
};
export default function Icon({
  name,
  size = 20,
  className = "",
  style,
}: {
  name: IconName;
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      className={className}
      style={style}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
