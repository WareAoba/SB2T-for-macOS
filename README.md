
맥북 용 식붕이툴
=============


[식붕이툴](https://github.com/JOWONRO/SB2Tool) , "SB2Tool")이 윈도우에서밖에 안 된다는 점이
너무나 한이 맺혀
직접 개발해보려고 합니다.

...사실 전 코딩 전문지식은 커녕
그냥 코딩할 줄도 모르고요

### [늦은밤의하트튠_마이너갤러리](https://gall.dcinside.com/mgallery/board/lists?id=heartune , "늦은 밤의 하트튠 마이너 갤러리")
파딱 한명이랑
파이썬 다룰 줄 아는 분이랑 같이
작업중입니다.



#당연히 알파 버전이라고 부르기도 민망한 수준입니다.

여러분의 도움이 필요합니다...
코딩 좀 도와주십쇼ㅠㅠ






# 사용법



당장 컴파일이 안돼있기 때문에

일단 **VSCode**로 불러오신 뒤
파이썬 디버거로 실행시켜주셔야 합니다.

**Main Quartz.py**가 원래 파일이고요,

SwiftAlt 브런치 내 **Main_Quartz.py** 파일은
프론트엔드 / 백엔드 이원화 실험중인 파일입니다.

_ <---- 밑줄 조심해서 사용해주세요.




# 지원되는 기능



1. txt 파일을 불러오면 각 문단별로 복사를 합니다.
  * 이 중, **페이지 번호**나 **페이지 구분선** 등 만화 대사가 아닌 것들은 자동으로 스킵합니다.
   
2. **Cmd + V**가 감지되면 자동으로 다음 문단을 복사합니다.
  * 클립보드를 감시하여, 역본에 없는 내용(ex:복사한 사진, 엉뚱한 다른 문장 등)이 붙여넣기 되면 프로그램이 자동으로 **일시정지**됩니다.

3. Opt + 화살표를 통해 이전/다음 문단으로 이동할 수 있습니다.
  *  ← → : 이전/다음 문단
  *  ↑ ↓ : 프로그램 일시정지/재개

4. **오버레이 창**에는 **이전/현재/다음 문단**이 표시됩니다.
  * 오버레이 창 크기 조절은 추후 넣을 예정

5. 프로그램을 종료할 때는 웬만하면 **파이썬 디버거 종료**를 통해 종료해주세요.
