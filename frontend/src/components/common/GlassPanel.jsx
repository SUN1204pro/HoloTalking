function GlassPanel({ children, className = "" }) {
  return (
    <div className={`glass-panel rounded-2xl shadow-2xl ${className}`}>
      {children}
    </div>
  );
}

export default GlassPanel;