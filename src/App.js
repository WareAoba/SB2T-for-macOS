import React, { useEffect, useState } from 'react';
import axios from 'axios';
import Overlay from './Overlay';

function App() {
  const [paragraphs, setParagraphs] = useState({
    previous: '',
    current: '',
    next: ''
  });
  const [filePath, setFilePath] = useState('');

  const loadFile = () => {
    axios.post('http://localhost:5000/load_file', {
      file_path: filePath
    }).then(response => {
      if (response.data.success) {
        fetchParagraphs();
      } else {
        alert('파일 로드 실패');
      }
    });
  };

  const fetchParagraphs = () => {
    axios.get('http://localhost:5000/get_paragraphs')
      .then(response => {
        setParagraphs(response.data);
      });
  };

  const nextParagraph = () => {
    axios.post('http://localhost:5000/next_paragraph')
      .then(() => fetchParagraphs());
  };

  const prevParagraph = () => {
    axios.post('http://localhost:5000/prev_paragraph')
      .then(() => fetchParagraphs());
  };

  useEffect(() => {
    fetchParagraphs();
  }, []);

  return (
    <div style={{ padding: '20px' }}>
      <h1>Paragraph Manager</h1>
      <div>
        <input 
          type="text" 
          value={filePath} 
          onChange={(e) => setFilePath(e.target.value)} 
          placeholder="파일 경로를 입력하세요"
          style={{ width: '300px' }}
        />
        <button onClick={loadFile}>파일 로드</button>
      </div>
      <div style={{ marginTop: '20px' }}>
        <button onClick={prevParagraph}>이전</button>
        <button onClick={nextParagraph}>다음</button>
      </div>
      <div style={{ marginTop: '20px' }}>
        <h2>현재 단락:</h2>
        <p>{paragraphs.current}</p>
        <h3>이전 단락:</h3>
        <p>{paragraphs.previous}</p>
        <h3>다음 단락:</h3>
        <p>{paragraphs.next}</p>
      </div>
      <Overlay 
        previous={paragraphs.previous} 
        current={paragraphs.current} 
        next={paragraphs.next} 
      />
    </div>
  );
}

export default App;