export default function TopBar() {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 0',
      borderBottom: '1px solid #eee',
      marginBottom: 12,
    }}>
      <span style={{ fontSize: 18, fontWeight: 700, color: '#1a1a2e' }}>竞品雷达</span>
      <span style={{ fontSize: 12, color: '#aaa' }}>产品竞争力评测</span>
    </div>
  );
}
