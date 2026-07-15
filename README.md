# Nebo Companion

Nebo에서 공유한 메모의 날짜와 시간을 인식해 Android 캘린더의 일정 추가 화면으로 전달하는 작은 앱입니다.

## 사용 흐름

1. Nebo에서 날짜와 시간이 들어 있는 메모를 선택합니다.
2. **공유** → **Nebo Companion**을 선택합니다.
3. 앱에서 인식한 일정 제목과 시간을 확인합니다.
4. **Google Calendar에 추가**를 눌러 캘린더에서 최종 저장합니다.

지원 예시:

- `내일 오후 3시 팀 회의`
- `7월 20일 오전 10시 치과`
- `2026-07-21 14:30 프로젝트 검토`
- `Friday at 2 PM weekly review`

날짜와 시간이 둘 다 있어야 일정으로 인식합니다. 연도가 없고 해당 날짜가 이미 지났다면 다음 해로 해석합니다. 일정 길이는 우선 1시간으로 설정됩니다.

## GitHub에서 APK 만들기

이 폴더의 내용 전체를 GitHub 저장소 루트에 올리고 `main` 브랜치에 커밋하면 **Actions → Build Android APK**가 자동 실행됩니다. 완료 후 실행 결과의 **Artifacts**에서 `nebo-companion-debug-apk`를 내려받아 압축을 풀면 `app-debug.apk`가 있습니다.

수동 실행은 **Actions → Build Android APK → Run workflow**를 누르면 됩니다.

## 로컬 빌드

JDK 17과 Gradle 8.7이 설치된 환경에서:

```bash
gradle testDebugUnitTest assembleDebug
```

APK 경로: `app/build/outputs/apk/debug/app-debug.apk`

## 개인정보

이 앱은 인터넷 권한이나 캘린더 읽기/쓰기 권한을 요청하지 않습니다. 공유받은 텍스트는 기기 안에서만 해석하고, Android 표준 일정 추가 화면에 전달합니다. 실제 저장은 사용자가 캘린더 화면에서 확정합니다.
