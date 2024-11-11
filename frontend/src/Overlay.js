// Overlay.js
import React from 'react';

function Overlay({ previous, current, next }) {
  // 스타일은 필요에 따라 변경
  const overlayStyle = {
    position: 'fixed',
    top: '10px',
    right: '10px',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    padding: '10px',
    borderRadius: '8px',
    width: '300px'
  };

  return (
    <div style={overlayStyle}>
      <h3>이전:</h3>
      <p>{previous}</p>
      <h2>현재:</h2>
      <p>{current}</p>
      <h3>다음:</h3>
      <p>{next}</p>
    </div>
  );
}

export default Overlay;