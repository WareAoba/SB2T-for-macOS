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

  const loadFile = async () => {
    const filePaths = await window.electron.openFile();
    if (filePaths.length > 0) {
      setFilePath(filePaths[0]);
      axios.post('http://localhost:5001/load_file', {
        file_path: filePaths[0]
      }).then(response => {
        if (response.data.success) {
          fetchParagraphs();
        } else {
          alert('파일 로드 실패');
        }
      }).catch(error => {
        console.error('파일 로드 중 오류 발생:', error);
      });
    }
  };

  const fetchParagraphs = () => {
    axios.get('http://localhost:5001/get_paragraphs')
      .then(response => {
        setParagraphs(response.data);
      }).catch(error => {
        console.error('단락 가져오기 중 오류 발생:', error);
      });
  };

  const nextParagraph = () => {
    axios.post('http://localhost:5001/next_paragraph')
      .then(() => fetchParagraphs())
      .catch(error => {
        console.error('다음 단락으로 이동 중 오류 발생:', error);
      });
  };

  const prevParagraph = () => {
    axios.post('http://localhost:5001/prev_paragraph')
      .then(() => fetchParagraphs())
      .catch(error => {
        console.error('이전 단락으로 이동 중 오류 발생:', error);
      });
  };

  useEffect(() => {
    fetchParagraphs();
  }, []);

  return (
    <div style={{ padding: '20px' }}>
      <h1>Paragraph Manager</h1>
      <div>
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