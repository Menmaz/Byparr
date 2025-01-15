from __future__ import annotations

import logging
import time
from http import HTTPStatus

import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sbase import SB, BaseCase

import src
import src.utils
import src.utils.consts
from src.models.requests import LinkRequest, LinkResponse, Solution
from src.utils import logger
from src.utils.consts import LOG_LEVEL, USE_HEADLESS, USE_XVFB

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)

cookies = []


@app.get("/")
def read_root():
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@app.get("/health")
async def health_check():
  try:
        response = requests.get("https://prowlarr.servarr.com/v1/ping")
        if response.status_code != HTTPStatus.OK:
            raise HTTPException(
                status_code=500,
                detail="Health check failed",
            )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check request failed: {e}",
        )

    return {"status": "ok"}


@app.post("/v1")
def read_item(request: LinkRequest) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    # request.url = "https://nowsecure.nl"
    logger.info(f"Request: {request}")

    # Check is string is url
    if not (request.url.startswith("http://") or request.url.startswith("https://")):
        return LinkResponse.invalid(request.url)

    response: LinkResponse

    # start_time = int(time.time() * 1000)
    with SB(
        uc=True,
        locale_code="en",
        test=False,
        ad_block=True,
        xvfb=USE_XVFB,
        headless=USE_HEADLESS,
    ) as sb:
        try:
            sb: BaseCase
            global cookies  # noqa: PLW0603
            if cookies:
                sb.uc_open_with_reconnect(request.url)
                sb.add_cookies(cookies)
            sb.uc_open_with_reconnect(request.url)
            source = sb.get_page_source()
            source_bs = BeautifulSoup(source, "html.parser")
            title_tag = source_bs.title
            logger.debug(f"Got webpage: {request.url}")
            if title_tag and title_tag.string in src.utils.consts.CHALLENGE_TITLES:
                logger.debug("Challenge detected")
                sb.uc_gui_click_captcha()
                logger.info("Clicked captcha")

            source = sb.get_page_source()
            source_bs = BeautifulSoup(source, "html.parser")
            title_tag = source_bs.title

            if title_tag and title_tag.string in src.utils.consts.CHALLENGE_TITLES:
                sb.save_screenshot(f"./screenshots/{request.url}.png")
                raise_captcha_bypass_error()

            response = {'html': source}
            cookies = sb.get_cookies()
        except Exception as e:
            logger.error(f"Error: {e}")
            if sb.driver:
                sb.driver.quit()
            raise HTTPException(
                status_code=500, detail="Unknown error, check logs"
            ) from e

    return response


def raise_captcha_bypass_error():
    """
    Raise a 500 error if the challenge could not be bypassed.

    This function should be called if the challenge is not bypassed after
    clicking the captcha.

    Returns:
        None

    """
    raise HTTPException(status_code=500, detail="Could not bypass challenge")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=LOG_LEVEL)  # noqa: S104
