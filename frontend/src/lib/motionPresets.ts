export const motionPresets = {
  page: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -6 },
    transition: { duration: 0.22, ease: "easeOut" as const },
  },
  card: {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.2, ease: "easeOut" as const },
    whileHover: { scale: 1.008 },
  },
  sidebar: {
    transition: { type: "spring" as const, stiffness: 260, damping: 30, mass: 0.9 },
  },
}
