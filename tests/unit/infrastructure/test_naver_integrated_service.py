import httpx

from viral_marketing_reporter.infrastructure.platforms.naver_integrated.service import (
    PlaywrightNaverIntegratedSearchService,
    normalize_naver_blog_url,
)


def test_normalize_naver_blog_url_handles_mobile_and_query_parameters():
    assert (
        normalize_naver_blog_url(
            "https://m.blog.naver.com/Choco520/224364092012?isInf=true"
        )
        == "choco520/224364092012"
    )
    assert (
        normalize_naver_blog_url("https://blog.naver.com/choco520/224364092012")
        == "choco520/224364092012"
    )


def test_normalize_naver_blog_url_rejects_non_post_urls():
    assert normalize_naver_blog_url("https://in.naver.com/choco520") is None
    assert normalize_naver_blog_url("https://blog.naver.com/choco520") is None
    assert normalize_naver_blog_url("https://example.com/choco520/224364092012") is None


async def test_resolve_influencer_url_follows_redirect_to_original_blog(mocker):
    service = PlaywrightNaverIntegratedSearchService(mocker.Mock())

    def redirect_to_blog(request: httpx.Request) -> httpx.Response:
        if request.url.host == "in.naver.com":
            return httpx.Response(
                302,
                headers={
                    "Location": (
                        "https://m.blog.naver.com/choco520/224364092012?isInf=true"
                    )
                },
            )
        return httpx.Response(200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(redirect_to_blog)
    ) as client:
        result = await service._resolve_influencer_url(
            client,
            "https://in.naver.com/choco/contents/internal/123456",
        )

    assert result == "choco520/224364092012"


async def test_resolve_influencer_url_rejects_untrusted_hosts(mocker):
    service = PlaywrightNaverIntegratedSearchService(mocker.Mock())
    async with httpx.AsyncClient() as client:
        result = await service._resolve_influencer_url(
            client,
            "https://example.com/choco/contents/internal/123456",
        )
    assert result is None


async def test_resolve_target_posts_accepts_blog_and_influencer_inputs(mocker):
    service = PlaywrightNaverIntegratedSearchService(mocker.Mock())
    influencer_url = "https://in.naver.com/choco/contents/123456"
    influencer_post = mocker.Mock(url=influencer_url)
    blog_post = mocker.Mock(
        url="https://blog.naver.com/nini0817/224364249261"
    )
    mocker.patch.object(
        service,
        "_resolve_influencer_url",
        return_value="choco520/224364092012",
    )

    result = await service._resolve_target_posts([influencer_post, blog_post])

    assert result == {
        "choco520/224364092012": influencer_post,
        "nini0817/224364249261": blog_post,
    }


async def test_resolve_influencer_url_accepts_internal_and_public_content_paths(
    mocker,
):
    service = PlaywrightNaverIntegratedSearchService(mocker.Mock())

    def redirect_to_blog(request: httpx.Request) -> httpx.Response:
        if request.url.host == "in.naver.com":
            return httpx.Response(
                302,
                headers={
                    "Location": "https://blog.naver.com/choco520/224364092012"
                },
            )
        return httpx.Response(200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(redirect_to_blog)
    ) as client:
        public_result = await service._resolve_influencer_url(
            client, "https://in.naver.com/choco/contents/123456"
        )
        internal_result = await service._resolve_influencer_url(
            client, "https://in.naver.com/choco/contents/internal/123456"
        )

    assert public_result == "choco520/224364092012"
    assert internal_result == "choco520/224364092012"
