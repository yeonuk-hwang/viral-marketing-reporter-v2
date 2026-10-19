# Instagram 해시태그 검색 오류 복구

## 접수 자료

- 오류 결과 화면: `temp_1792320522555.352061267.png`
- 연속 로그: `debug.2026-09-22_09-47-36_959199.log`, `kat2E98.tmp`
- 대상 게시물: `https://www.instagram.com/p/DefupcqTpxj/`
- 발생 시각: 2026-10-16 17:04~17:07 KST
- 키워드: 팸퍼스, 터치오브네이처팬티, 엔젤브리즈팬티, 기저귀추천,
  프리미엄기저귀

## 원인

저장된 로그인 세션 검증은 정상적으로 성공했고 대상 게시물 주소도 HTTP 200으로
열렸다. 주소 매칭이나 로그인 만료가 원인이 아니었다.

앱은 정상적인 해시태그 검색 의미를 유지하기 위해 각 키워드를 `#키워드`로
요청했다. 그러나 제공된 실행 환경에서 Instagram이 모든 해시태그 요청에 다음
오류 화면을 반환했다.

```text
title: Page couldn't load • Instagram
body: Something went wrong. There's an issue and the page could not be loaded.
post_count: 0
GraphQL error: 1675030
operation: PolarisHashtagHeaderActionButtonsQuery
```

응답 문서의 HTTP 상태는 200이었으므로 단순 네트워크 상태 코드 검사로는 이
오류를 알 수 없다. 기존 앱은 게시물 링크를 15초 기다린 뒤 페이지 상태 오류로
처리했고, 동일한 현상이 다섯 키워드에 모두 발생했다.

동일 세션과 브라우저에서 비교한 결과는 다음과 같았다.

```text
#팸퍼스: Page couldn't load, 게시물 0개
팸퍼스: 정상 페이지, 게시물 24개
```

브라우저 User-Agent와 언어를 세 가지 조합으로 바꿔도 해시태그 요청은 모두
동일한 GraphQL 오류를 반환했다.

추가로 `#cats`, `#travel`, `#팸퍼스`를 데스크톱 웹에서 비교했으며 세 태그
모두 같은 오류가 발생했다. Pixel 7 환경으로 에뮬레이션한 모바일 웹에서도
`#cats`와 `#팸퍼스`가 동일하게 실패했다. 따라서 특정 한국어 태그가 아니라
Instagram 웹 해시태그 경로의 광범위한 문제로 판단된다.

이 검사는 모바일 **웹**까지의 결과다. 네이티브 iOS/Android Instagram 앱은
이 환경에서 직접 실행하지 않았으므로 앱 내부 검색 장애까지 확인된 것은 아니다.
Instagram 공식 도움말은 모바일 앱에서 게시물 아래의 해시태그를 탭하면 해당
해시태그 결과 페이지를 연다고 여전히 안내한다.

## 수정

데스크톱 웹의 해시태그 경로가 광범위하게 실패하고, 오류를 확인한 뒤 다시
검색하면 모든 키워드가 불필요하게 느려진다. 따라서 데스크톱 자동화 검색은
처음부터 `#`을 제거한 `키워드` 일반 검색을 한 번 실행하도록 변경했다.

사용자가 입력값에 `#`을 포함해도 검색 요청에서 제거한다. 로그인,
challenge/checkpoint, 검색 제한 및 일반 키워드 페이지 자체의 오류 감지는
기존대로 유지한다.

## 검증

제공된 다섯 키워드를 수정된 실제 Playwright 흐름으로 실행했다.

```text
팸퍼스             completed, plain_keyword, 게시물 24개
터치오브네이처팬티  completed, plain_keyword, 게시물 24개
엔젤브리즈팬티      completed, plain_keyword, 게시물 24개
기저귀추천          completed, plain_keyword, 게시물 24개
프리미엄기저귀      completed, plain_keyword, 게시물 24개
```

따라서 다섯 작업 모두 더 이상 `에러 발생`으로 종료되지 않는다. 확인일인
2026-10-18에는 대상 게시물이 일반 검색의 현재 상위 10개에는 없었다. 검색
순위는 시점·계정에 따라 바뀌므로 이는 오류 복구 여부와 별개의 결과다.

- Instagram 관련 단위 테스트 통과
- 전체 infrastructure 단위 테스트 통과
