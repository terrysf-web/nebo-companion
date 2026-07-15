# Nebo Companion

Nebo에서 공유한 메모의 날짜와 시간을 인식해 Android 캘린더의 일정 추가 화면으로 전달하는 작은 앱입니다.

## 사용 흐름

1. Nebo에서 날짜와 시간이 들어 있는 메모를 선택합니다.
2. **공유** → **Nebo Companion**을 선택합니다.
3. 앱에서 인식한 일정 제목과 시간을 확인합니다.
4. **일정과 리마인더 저장**을 눌러 Google Calendar에 저장합니다.

지원 예시:

- `내일 오후 3시 팀 회의`
- `7월 20일 오전 10시 치과`
- `2026-07-21 14:30 프로젝트 검토`
- `Friday at 2 PM weekly review`
- `7월 20일 오후 3시 병원 예약, 1시간 전에 알려줘`

날짜와 시간이 둘 다 있어야 일정으로 인식합니다. 연도가 없고 해당 날짜가 이미 지났다면 다음 해로 해석합니다. 일정 길이는 우선 1시간입니다. `10분 전`, `1시간 전`, `하루 전` 같은 표현을 인식하며, 표현이 없으면 30분 전 알림을 사용합니다.

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

이 앱은 인터넷 권한을 요청하지 않습니다. 공유받은 텍스트는 기기 안에서만 해석합니다. 일정과 리마인더를 저장하기 위해 Android 캘린더 읽기/쓰기 권한을 한 번 요청하며, 기본 Google Calendar가 있으면 그 캘린더를 우선 사용합니다.
