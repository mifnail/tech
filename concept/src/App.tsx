import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { StoreProvider, useStore, useHashRoute } from './lib/core';
import { Stage, StatusBar, TabBar } from './components/Shell';
import { Toasts } from './components/ui';
import Home from './pages/Home';
import Lesson from './pages/Lesson';
import Gradebook from './pages/Gradebook';
import Schedule from './pages/Schedule';
import Students from './pages/Students';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';

/* ---------- роутер: паритет с оригинальными маршрутами ---------- */

function Routed({ route }: { route: string }) {
  const base = route.split('?')[0];
  let page: React.ReactNode;
  let key = base;

  if (base.startsWith('#lesson/')) {
    const id = Number(base.split('/')[1]);
    page = <Lesson id={id} />; key = `lesson-${id}`;
  } else if (base.startsWith('#subject/')) {
    const id = Number(base.split('/')[1]);
    page = <Gradebook id={id} />; key = `subject-${id}`;
  } else if (base.startsWith('#students/')) {
    const id = Number(base.split('/')[1]);
    page = <Students groupId={id} />; key = `students-${id}`;
  } else if (base.startsWith('#schedule')) {
    page = <Schedule />;
  } else if (base.startsWith('#analytics')) {
    page = <Analytics />;
  } else if (base.startsWith('#settings')) {
    page = <Settings />;
  } else {
    page = <Home />; key = 'home';
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={key}
        initial={{ opacity: 0, y: 18, filter: 'blur(6px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        exit={{ opacity: 0, y: -12, filter: 'blur(6px)' }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="min-h-full"
      >
        {page}
      </motion.div>
    </AnimatePresence>
  );
}

/* ---------- сплэш ---------- */

function Splash({ done }: { done: () => void }) {
  useEffect(() => {
    const t = setTimeout(done, 1200);
    return () => clearTimeout(t);
  }, [done]);
  return (
    <motion.div
      className="absolute inset-0 z-[80] grid place-items-center bg-panel"
      exit={{ opacity: 0, scale: 1.06, filter: 'blur(10px)' }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="text-center">
        <motion.div
          initial={{ scale: 0.5, opacity: 0, rotate: -8 }}
          animate={{ scale: 1, opacity: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 18 }}
          className="w-[72px] h-[72px] mx-auto rounded-[22px] grid place-items-center font-display text-[22px] font-bold"
          style={{
            background: 'linear-gradient(150deg,#7c8cff,#8b5cf6)',
            boxShadow: '0 20px 44px -12px rgba(124,140,255,.65), inset 0 1px 0 rgba(255,255,255,.3)',
          }}
        >
          Ж<span className="text-white/60">/</span>П
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="mt-4 font-display text-[12px] font-semibold tracking-[0.22em] uppercase text-white/55"
        >
          журнал преподавателя
        </motion.div>
        <motion.div
          className="mt-4 mx-auto h-[3px] w-28 rounded-full overflow-hidden bg-white/[.08]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg,#3ddc97,#7c8cff)' }}
            initial={{ width: '0%' }} animate={{ width: '100%' }}
            transition={{ duration: 0.85, ease: [0.4, 0, 0.2, 1], delay: 0.25 }}
          />
        </motion.div>
      </div>
    </motion.div>
  );
}

/* ---------- оболочка приложения ---------- */

function AppInner() {
  const route = useHashRoute();
  const { st, dismissToast } = useStore();
  const [booted, setBooted] = useState(false);

  return (
    <Stage>
      <StatusBar />
      <div id="screen" className="relative flex-1 overflow-y-auto no-scrollbar overscroll-contain">
        {booted && <Routed route={route} />}
      </div>
      {booted && <TabBar route={route} />}
      <Toasts toasts={st.toasts} onDismiss={dismissToast} />
      <AnimatePresence>
        {!booted && <Splash done={() => setBooted(true)} />}
      </AnimatePresence>
    </Stage>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <AppInner />
    </StoreProvider>
  );
}
