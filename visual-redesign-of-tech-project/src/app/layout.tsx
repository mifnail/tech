import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
export const metadata: Metadata = { title: 'TeachHelper — журнал преподавателя', description: 'Ваш учебный день под контролем. Занятия, группы, оценки и посещаемость в одном месте.' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ru"><head><link rel="stylesheet" href="/static/style.css" /><link rel="stylesheet" href="/static/redesign.css" /><link rel="icon" href="/icon.svg" type="image/svg+xml" /></head><body>{children}</body></html>;
}
