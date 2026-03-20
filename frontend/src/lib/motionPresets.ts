export const motionPresets = {
  page: {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -8 },
    transition: { duration: 0.24, ease: "easeOut" as const },
  },
  card: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.22, ease: "easeOut" as const },
    whileHover: { scale: 1.01 },
  },
  sidebar: {
    transition: { type: "spring" as const, stiffness: 280, damping: 28 },
  },
}
