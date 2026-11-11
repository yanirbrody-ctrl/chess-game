"""Browser tests for the Undo button and its ghost-move preview.

They drive the real page in Chrome through Playwright. If Playwright or Chrome is not
available, they are skipped instead of failing.
"""

import re
import threading

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from server import make_server  # noqa: E402

expect.set_options(timeout=10_000)
PIECES = ".square .piece:not(.ghost)"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        try:
            chrome = playwright.chromium.launch(channel="chrome", headless=True)
        except Exception as error:  # no Chrome installed, or it could not start
            pytest.skip(f"Chrome could not be started: {error}")
        yield chrome
        chrome.close()


@pytest.fixture
def page(browser):
    server = make_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tab = browser.new_page()
    tab.goto(f"http://127.0.0.1:{server.server_port}/")
    tab.wait_for_selector(".square")
    yield tab
    tab.close()
    server.shutdown()
    server.server_close()


def square(page, name):
    return page.locator(f'[data-square="{name}"]')


def move(page, source, target):
    """Click a piece, then its destination, and wait until the move shows on the board."""
    square(page, source).click()
    expect(square(page, source)).to_have_class(re.compile("selected"))
    square(page, target).click()
    expect(square(page, target).locator(".piece:not(.ghost)")).to_have_count(1)


def hover_undo(page):
    page.locator("#undo").hover()


def leave_undo(page):
    page.mouse.move(0, 0)


def test_undo_is_disabled_until_a_move_is_played(page):
    expect(page.locator("#undo")).to_be_disabled()
    move(page, "e2", "e4")
    expect(page.locator("#undo")).to_be_enabled()


def test_clicking_undo_puts_the_piece_back_and_gives_the_turn_back(page):
    move(page, "e2", "e4")
    page.locator("#undo").click()
    expect(square(page, "e2").locator(".piece:not(.ghost)")).to_have_count(1)
    expect(square(page, "e4").locator(".piece")).to_have_count(0)
    expect(page.locator("#turn")).to_have_text("White to move")
    expect(page.locator("#moves li")).to_have_count(0)
    expect(page.locator("#undo")).to_be_disabled()


def test_after_undo_a_different_piece_can_be_moved(page):
    move(page, "e2", "e4")
    page.locator("#undo").click()
    move(page, "d2", "d4")
    expect(square(page, "e2").locator(".piece:not(.ghost)")).to_have_count(1)
    expect(square(page, "e4").locator(".piece")).to_have_count(0)
    expect(page.locator("#moves li span")).to_have_text(["d2-d4"])


def test_undoing_a_check_removes_the_check_message(page):
    move(page, "e2", "e4")
    move(page, "f7", "f6")
    move(page, "d1", "h5")
    expect(page.locator("#turn")).to_contain_text("Check")
    page.locator("#undo").click()
    expect(page.locator("#turn")).to_have_text("White to move")


def test_hovering_undo_shows_a_ghost_an_arrow_and_a_caption(page):
    move(page, "e2", "e4")
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e2-e4")
    expect(square(page, "e2").locator(".piece.ghost.white")).to_have_count(1)
    expect(square(page, "e4").locator(".piece.fading")).to_have_count(1)
    expect(page.locator(".undo-arrows line")).to_have_count(1)


def test_moving_away_from_undo_removes_the_whole_preview(page):
    move(page, "e2", "e4")
    hover_undo(page)
    expect(page.locator(".piece.ghost")).to_have_count(1)
    leave_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("")
    expect(page.locator(".piece.ghost")).to_have_count(0)
    expect(page.locator(".piece.fading")).to_have_count(0)
    expect(page.locator(".undo-arrows")).to_have_count(0)
    expect(page.locator(".square.undo-change")).to_have_count(0)


def test_the_preview_changes_nothing_in_the_game(page):
    move(page, "e2", "e4")
    hover_undo(page)
    expect(page.locator(PIECES)).to_have_count(32)
    expect(page.locator("#moves li span")).to_have_text(["e2-e4"])
    expect(page.locator("#turn")).to_have_text("Black to move")
    expect(square(page, "e4").locator(".piece:not(.ghost)")).to_have_count(1)


def test_keyboard_focus_on_undo_shows_the_preview_too(page):
    move(page, "e2", "e4")
    page.locator("#undo").focus()
    expect(page.locator("#undo-caption")).to_have_text("Take back e2-e4")
    expect(page.locator(".undo-arrows line")).to_have_count(1)
    page.locator("#undo").blur()
    expect(page.locator("#undo-caption")).to_have_text("")
    expect(page.locator(".undo-arrows")).to_have_count(0)


def test_clicking_undo_clears_the_preview(page):
    move(page, "e2", "e4")
    move(page, "e7", "e5")
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e7-e5")
    page.locator("#undo").click()
    expect(page.locator("#moves li span")).to_have_text(["e2-e4"])
    expect(page.locator("#undo-caption")).to_have_text("")
    expect(page.locator(".piece.ghost")).to_have_count(0)


def test_the_preview_follows_the_latest_move_each_time(page):
    move(page, "e2", "e4")
    move(page, "e7", "e5")
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e7-e5")
    page.locator("#undo").click()
    leave_undo(page)
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e2-e4")


def test_the_preview_of_a_capture_shows_the_captured_piece_as_a_ghost(page):
    move(page, "e2", "e4")
    move(page, "d7", "d5")
    move(page, "e4", "d5")
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e4xd5")
    expect(square(page, "e4").locator(".piece.ghost.white")).to_have_count(1)
    expect(square(page, "d5").locator(".piece.ghost.black")).to_have_count(1)
    expect(square(page, "d5").locator(".piece.fading")).to_have_count(1)
    leave_undo(page)
    page.locator("#undo").click()
    expect(page.locator(PIECES)).to_have_count(32)
    expect(square(page, "d5").locator(".piece.black:not(.ghost)")).to_have_count(1)


def test_undoing_a_capture_removes_it_from_the_captured_display(page):
    move(page, "e2", "e4")
    move(page, "d7", "d5")
    move(page, "e4", "d5")
    expect(page.locator("#captured .piece")).to_have_count(1)
    page.locator("#undo").click()
    expect(page.locator("#captured .piece")).to_have_count(0)
    expect(page.locator("#captured")).to_have_text("None")


def test_against_the_computer_undo_takes_back_both_moves(page):
    page.get_by_role("button", name="New game: play the computer").click()
    move(page, "e2", "e4")
    expect(page.locator("#moves li span")).to_have_count(2)
    expect(page.locator("#turn")).to_have_text("Your move")
    hover_undo(page)
    expect(page.locator(".undo-arrows line")).to_have_count(2)
    expect(page.locator("#undo-caption")).to_contain_text("Take back e2-e4")
    leave_undo(page)
    page.locator("#undo").click()
    expect(page.locator("#moves li")).to_have_count(0)
    expect(page.locator("#turn")).to_have_text("Your move")
    expect(page.locator(PIECES)).to_have_count(32)
    expect(square(page, "e2").locator(".piece:not(.ghost)")).to_have_count(1)
    expect(page.locator("#undo")).to_be_disabled()


def test_new_game_clears_what_could_be_undone(page):
    move(page, "e2", "e4")
    page.get_by_role("button", name="New game: two players").click()
    expect(page.locator("#undo")).to_be_disabled()
    expect(page.locator("#moves li")).to_have_count(0)
    expect(page.locator("#turn")).to_have_text("White to move")


def test_undoing_a_promotion_in_the_browser(page):
    for source, target in [("a2", "a4"), ("h7", "h5"), ("a4", "a5"), ("h5", "h4"),
                           ("a5", "a6"), ("h4", "h3"), ("a6", "b7"), ("h3", "g2")]:
        move(page, source, target)
    expect(page.locator("#captured .piece")).to_have_count(2)
    square(page, "b7").click()
    expect(square(page, "b7")).to_have_class(re.compile("selected"))
    square(page, "a8").click()
    page.locator('#promotion-choices button[aria-label="queen"]').click()
    expect(square(page, "a8").locator(".piece.white:not(.ghost)")).to_have_count(1)
    expect(page.locator("#captured .piece")).to_have_count(3)
    page.locator("#undo").click()
    expect(square(page, "b7").locator(".piece.white:not(.ghost)")).to_have_count(1)
    expect(square(page, "a8").locator(".piece.black:not(.ghost)")).to_have_count(1)
    expect(page.locator("#captured .piece")).to_have_count(2)
    expect(page.locator("#turn")).to_have_text("White to move")


def save_to_file(page):
    with page.expect_download() as download:
        page.locator("#save").click()
    return download.value.path()


def test_saving_and_loading_in_the_browser_keeps_captures_and_undo(page):
    move(page, "e2", "e4")
    move(page, "d7", "d5")
    move(page, "e4", "d5")
    saved = save_to_file(page)
    page.get_by_role("button", name="New game: two players").click()
    expect(page.locator("#moves li")).to_have_count(0)
    expect(page.locator("#undo")).to_be_disabled()
    page.locator("#load-file").set_input_files(saved)
    expect(page.locator("#moves li span")).to_have_count(3)
    expect(page.locator("#captured .piece")).to_have_count(1)
    expect(page.locator("#undo")).to_be_enabled()
    page.locator("#undo").click()
    expect(page.locator("#moves li span")).to_have_count(2)
    expect(page.locator("#captured .piece")).to_have_count(0)
    expect(square(page, "d5").locator(".piece.black:not(.ghost)")).to_have_count(1)


def test_a_loaded_game_shows_the_undo_preview(page):
    move(page, "e2", "e4")
    saved = save_to_file(page)
    page.get_by_role("button", name="New game: two players").click()
    page.locator("#load-file").set_input_files(saved)
    expect(page.locator("#moves li span")).to_have_text(["e2-e4"])
    hover_undo(page)
    expect(page.locator("#undo-caption")).to_have_text("Take back e2-e4")
    expect(page.locator(".undo-arrows line")).to_have_count(1)


def test_loading_a_file_that_is_not_a_save_keeps_the_game(page, tmp_path):
    move(page, "e2", "e4")
    bad = tmp_path / "not-a-save.json"
    bad.write_text('{"hello": 1}')
    page.locator("#load-file").set_input_files(str(bad))
    expect(page.locator("#message")).to_contain_text("Invalid save file")
    expect(page.locator("#moves li span")).to_have_text(["e2-e4"])
