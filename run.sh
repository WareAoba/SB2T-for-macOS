#!/bin/bash

# 백엔드 실행
echo "백엔드를 실행합니다..."
cd backend
python3 Main.py &
BACKEND_PID=$!
cd ..

# 프론트엔드 실행
echo "프론트엔드를 실행합니다..."
cd frontend
export NODE_OPTIONS=--openssl-legacy-provider
npm start
cd ..

# 실행이 끝나면 백엔드 프로세스 종료
kill $BACKEND_PID