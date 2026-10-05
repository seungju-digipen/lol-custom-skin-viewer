# LoL Custom Skin Viewer

Windows용 로컬 League of Legends 커스텀 스킨 모델 뷰어입니다. 모드를 읽고 설치된 게임의 원본 애니메이션을 연결합니다.

## 기능

- ZIP / FANTOME 및 압축 해제한 폴더 가져오기
- 상위 폴더를 한 번 저장하고 모드 목록에서 선택
- 선택한 모드만 변환하고 결과를 캐시
- 회전, 확대, 애니메이션 선택, 재생 속도 및 배경색 조절
- TEX / DDS 텍스처와 BIN의 재질별 텍스처 연결
- 원본보다 모드 텍스처 우선, 기본 숨김 메시 처리
- 애니메이션 없는 기본 자세 확인

## 설치와 실행

Windows x64, Python 3.11 이상, 설치된 League of Legends와 초기 인터넷 연결이 필요합니다.

1. PowerShell에서 `./setup.ps1`을 실행합니다. 필요한 변환 도구와 .NET 8 런타임은 `tools/`에 내려받습니다.
2. `config.json`의 `champions_dir`을 게임의 `Game/DATA/FINAL/Champions` 폴더로 설정합니다. 또는 `LOL_CHAMPIONS_DIR` 환경변수를 사용합니다.
3. `start.cmd`를 실행합니다.
4. 브라우저에서 http://127.0.0.1:8766/ 을 엽니다.

모드 파일은 로컬에서 처리합니다. 프런트엔드 3D 뷰어 라이브러리는 Google CDN에서 로드하므로 인터넷 연결이 필요합니다. 서버는 127.0.0.1에만 바인딩되며, 원본 게임 파일은 수정하지 않습니다.

## 사용

한 모드는 ZIP/FANTOME을 선택하고 **모드 열기**를 누릅니다. 여러 모드는 **모드 모음 폴더**로 상위 폴더를 업로드한 뒤 **저장된 폴더 → 모드 목록 → 선택한 모드 보기**를 사용합니다. 라이브러리와 캐시는 `.data/`에 저장됩니다. 개별 파일은 최대 300MB, 프런트엔드 폴더 업로드는 최대 5GB입니다.

## 현재 한계

- 첫 번째 모델을 표시합니다. 복수 모델·형태를 모두 선택하는 기능은 없습니다.
- 게임 셰이더, 스킬 이펙트, 음성, 애니메이션별 소품 표시/숨김을 재현하지 않습니다.
- 커스텀 뼈대와 원본 애니메이션이 다르면 변형이 깨질 수 있습니다.
- TEX/DDS와 BIN 형식에 따라 변환이 실패하거나 파일명 추정으로 연결될 수 있습니다.
- RAR/7Z는 먼저 압축 해제해야 합니다.
- 로컬 개인용 프로토타입입니다. 외부 네트워크에 공개하는 서버로 설계하지 않았습니다.

## 코드와 외부 도구

- `server.py`: 업로드, 모드 목록, 원본 추출, 텍스처 매핑, GLB 변환 API
- `index.html`: 브라우저 UI
- `setup.ps1`: 로컬 의존성 설치
- [lol2gltf](https://github.com/Crauzer/lol2gltf)
- [wadtools](https://github.com/LeagueToolkit/wadtools)
- [ltk-tex-utils](https://github.com/LeagueToolkit/ltk-tex-utils)
- [ritobin](https://github.com/moonshadow565/ritobin)
- [model-viewer](https://github.com/google/model-viewer)

외부 실행 파일은 저장소에 포함하지 않으며 각 도구의 라이선스가 적용됩니다. 롤 원본 데이터, 커스텀 모드, 모델, 이미지, 개인 파일 경로는 포함하지 않습니다. Riot Games와 제휴하지 않은 도구입니다.
