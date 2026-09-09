import type { CSSProperties } from 'react';
export type IconName = 'sun' | 'calendar' | 'users' | 'book' | 'journal' | 'chart' | 'settings' | 'help' | 'chevron' | 'left' | 'plus' | 'search' | 'bell' | 'arrow' | 'check' | 'clock' | 'more' | 'download' | 'shield' | 'logout' | 'close' | 'play' | 'file' | 'wifi' | 'mail' | 'filter' | 'menu' | 'check-circle' | 'leaf';
const paths: Record<IconName, React.ReactNode> = {
 sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
 calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18m-13 4h1m6 0h1m-8 3h1m6 0h1"/></>,
 users: <><circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5"/></>,
 book: <><path d="M12 5v16M12 5C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1Z"/></>,
 journal: <><rect x="5" y="3" width="15" height="18" rx="2"/><path d="M9 3v18M3 7h4m-4 5h4m-4 5h4m6-9h4m-4 4h4"/></>,
 chart: <><path d="M4 3v17h17M8 15v-4m5 4V6m5 9V9"/></>,
 settings: <><path d="m9 3-.5 2-2 1L4 5.5 2.5 8l1.5 1.5v3L2.5 14 4 17l2.5-.5 2 1L9 20h4l.5-2.5 2-1 2.5.5 1.5-3-1.5-1.5v-3L19.5 8 18 5.5 2.5.5-2-1L13 3Z" transform="translate(1 0)"/><circle cx="12" cy="11.5" r="3"/></>,
 help: <><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/></>,
 chevron: <path d="m9 5 7 7-7 7"/>, left: <path d="m15 5-7 7 7 7"/>, plus: <path d="M12 5v14M5 12h14"/>, search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>,
 bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
 arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>, check: <path d="m5 12 4 4L19 6"/>, clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
 more: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
 download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>, shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-5"/></>,
 logout: <><path d="M10 3H4v18h6m-1-9h12m-4-4 4 4-4 4"/></>, close: <path d="m6 6 12 12M6 18 18 6"/>, play: <path d="m8 4 12 8-12 8Z"/>, file: <><path d="M14 2H5v20h14V7Zm0 0v6h5M8 13h8m-8 4h6"/></>,
 wifi: <><path d="M3 8a15 15 0 0 1 18 0M6 12a10 10 0 0 1 12 0m-9 4a5 5 0 0 1 6 0"/><circle cx="12" cy="20" r=".5"/></>,
 mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/></>, filter: <><path d="M3 6h18M6 12h12m-8 6h4"/></>, menu: <path d="M4 6h16M4 12h16M4 18h16"/>, 'check-circle': <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>, leaf: <><path d="M20 3C9 2 2 9 6 16s15 2 14-13ZM5 21 16 9"/></>,
};
export default function Icon({name, size = 20, className = '', style}: {name: IconName; size?: number; className?: string; style?: CSSProperties}) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true">{paths[name]}</svg>; }
