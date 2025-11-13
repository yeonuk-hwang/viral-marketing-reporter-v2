"""Instagram 플랫폼 테스트 스크립트

새로운 Instagram 로그인 흐름 테스트:
1. 스크립트 실행
2. 저장된 세션이 없으면 자동으로 headful 브라우저가 열림
3. 로그인 완료 후 브라우저를 닫으면 세션이 저장됨
4. headless 모드로 자동 검색 및 매칭 수행
5. 다음 실행부터는 저장된 세션으로 바로 실행됨
"""

import asyncio
from pathlib import Path

from viral_marketing_reporter import bootstrap
from viral_marketing_reporter.domain.model import Keyword, Platform, Post
from viral_marketing_reporter.infrastructure.context import ApplicationContext


async def run_test():
    print("=" * 60)
    print("Instagram 플랫폼 테스트")
    print("=" * 60)

    # 테스트 데이터
    keyword = Keyword(text="이천데이트")
    posts_to_find = [
        Post(url="https://www.instagram.com/p/C7jcvNiP02_/"),  # 3번째 포스트
        Post(url="https://www.instagram.com/p/DAk8sbeSsGw/"),  # 6번째 포스트
    ]
    output_dir = Path.home() / "Downloads" / "viral-reporter" / "instagram" / "test"

    print(f"\n검색 키워드: {keyword.text}")
    print(f"찾을 포스트 URL:")
    for i, post in enumerate(posts_to_find, 1):
        print(f"  {i}. {post.url}")
    print(f"\n스크린샷 저장 경로: {output_dir}")

    async with ApplicationContext() as context:
        print("\nApplicationContext 초기화 완료 (headless 모드)")

        # Bootstrap으로 애플리케이션 초기화
        print("\n애플리케이션 bootstrap 시작...")
        application = bootstrap.bootstrap(context)

        print("\n" + "=" * 60)
        print("Instagram 인증을 준비합니다...")
        print("(저장된 세션이 없으면 로그인 창이 자동으로 열립니다)")
        print("=" * 60)

        # 플랫폼 사전 준비 (인증)
        await application.factory.prepare_platforms({Platform.INSTAGRAM})

        print("\n" + "=" * 60)
        print("Instagram 서비스를 가져옵니다...")
        print("=" * 60)

        try:
            # Instagram 서비스 가져오기
            service = await application.factory.get_service(Platform.INSTAGRAM)

            print("\n검색을 시작합니다...")

            result = await service.search_and_find_posts(
                index=1,
                keyword=keyword,
                posts_to_find=posts_to_find,
                output_dir=output_dir,
            )

            print("\n" + "=" * 60)
            print("검색 완료!")
            print("=" * 60)
            print(f"\n찾은 포스트 개수: {len(result.found_posts)}")

            if result.found_posts:
                print("\n매칭된 포스트:")
                for i, post in enumerate(result.found_posts, 1):
                    print(f"  {i}. {post.url}")

            if result.screenshot:
                print(f"\n스크린샷 저장: {result.screenshot.file_path}")
                print(f"파일 존재: {result.screenshot.file_path.exists()}")
            else:
                print("\n스크린샷 없음 (매칭된 포스트가 없습니다)")

        except Exception as e:
            print(f"\n오류 발생: {e}")
            import traceback

            traceback.print_exc()
            raise

        finally:
            # Factory 리소스 정리
            await application.factory.cleanup()

    print("\n테스트 완료!")
    print("\n💡 Tip: 저장된 세션을 삭제하려면:")
    print("   rm ~/Downloads/viral-reporter/instagram_session.json")


def main():
    """테스트 스크립트 진입점"""
    asyncio.run(run_test())


if __name__ == "__main__":
    main()
