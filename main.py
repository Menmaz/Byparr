from __future__ import annotations

import logging
import time

import uvicorn.config
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sbase import SB, BaseCase

import src
import src.utils
import src.utils.consts
from src.models.requests import LinkRequest, LinkResponse, Solution
from src.utils import logger
from src.utils.consts import LOG_LEVEL

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)


@app.get("/")
def read_root():
    """Redirect to /docs."""
    logger.info("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check")

    health_check_request = read_item(
        LinkRequest.model_construct(url="https://prowlarr.servarr.com/v1/ping")
    )
    if health_check_request.solution.status != 200:
        raise HTTPException(
            status_code=500,
            detail="Health check failed",
        )

    return {"status": "ok"}


@app.post("/v1")
def read_item(request: LinkRequest):
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    # request.url = "https://nowsecure.nl"
    logger.info(f"Request: {request}")
    response: LinkResponse

    # start_time = int(time.time() * 1000)
    try:
        with SB(uc=True, locale_code="en", test=False, xvfb=True, ad_block=True) as sb:
            sb: BaseCase
            sb.uc_open_with_reconnect(request.url)
            source = sb.get_page_source()
            source_bs = BeautifulSoup(source, "html.parser")
            title_tag = source_bs.title
            logger.info(f"Got webpage: {request.url}")
            if title_tag and title_tag.string in src.utils.consts.CHALLENGE_TITLES:
                logger.info("Challenge detected")
                sb.uc_gui_click_captcha()
                logger.info("Clicked captcha")

            source = sb.get_page_source()
            source_bs = BeautifulSoup(source, "html.parser")
            title_tag = source_bs.title

            if title_tag and title_tag.string in src.utils.consts.CHALLENGE_TITLES:
                sb.save_screenshot(f"./screenshots/{request.url}.png")
                raise HTTPException(
                    status_code=500, detail="Could not bypass challenge"
                )

            response = LinkResponse(
                message="Success",
                solution=Solution(
                    userAgent=sb.get_user_agent(),
                    url=sb.get_current_url(),
                    status=200,
                    cookies=sb.get_cookies(),
                    headers={},
                    response=source,
                ),
                startTimestamp=start_time,
            )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Unknown error, check logs") from e

    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=LOG_LEVEL)  # noqa: S104
