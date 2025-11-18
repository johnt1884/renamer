
import asyncio
import re
import os
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Listen for console logs
        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))

        # Correctly get the absolute path to the local HTML file
        file_path = os.path.abspath('renamer.html')
        await page.goto(f"file://{file_path}")

        # Wait for the page to fully load, ensuring the init() script has run
        await page.wait_for_load_state('load')

        # Override the File System Access API to mock a directory
        await page.evaluate("""
            () => {
                window.showDirectoryPicker = async () => {
                    return {
                        name: 'test-dir',
                        kind: 'directory',
                        queryPermission: async () => 'granted',
                        values: async function*() {
                            yield {
                                kind: 'file',
                                name: 'video1.mp4',
                                getFile: async () => new File([], 'video1.mp4', { lastModified: 1731859200000 }) // Nov 17, 2024
                            };
                            yield {
                                kind: 'file',
                                name: 'video2.mp4',
                                getFile: async () => new File([], 'video2.mp4', { lastModified: 1731862800000 }) // Nov 17, 2024 +1hr
                            };
                            yield {
                                kind: 'file',
                                name: 'video3.mp4',
                                getFile: async () => new File([], 'video3.mp4', { lastModified: 1731855600000 }) // Nov 17, 2024 -1hr
                            };
                            yield {
                                kind: 'directory',
                                name: 'Landscape',
                                values: async function*() {
                                    yield {
                                        kind: 'file',
                                        name: 'video1.mp4',
                                        getFile: async () => new File([], 'video1.mp4')
                                    };
                                }
                            };
                             yield {
                                kind: 'directory',
                                name: 'sc',
                                values: async function*() {
                                    yield {
                                        kind: 'file',
                                        name: 'video2.mp4.lnk',
                                        getFile: async () => new File([], 'video2.mp4.lnk')
                                    };
                                }
                            };
                        }
                    };
                };
            }
        """)

        # Corrected the selector here
        await page.click('#load-directory-btn')

        # Wait for thumbnails to be generated
        await expect(page.locator('.thumbnail-wrapper')).to_have_count(3)

        # Click the "Edit Mode" button
        await page.click('#edit-mode-toggle')

        # Wait for the UI to update for Edit Mode. The button text changes, which is a good signal.
        await expect(page.locator('#edit-mode-btn')).to_have_text('Edit Mode On')

        # Verify the outlines are applied
        video1_wrapper = page.locator('.thumbnail-wrapper', has_text='video1.mp4')
        await expect(video1_wrapper).to_have_class(re.compile(r"selected-landscape"))

        video2_wrapper = page.locator('.thumbnail-wrapper', has_text='video2.mp4')
        await expect(video2_wrapper).to_have_class(re.compile(r"selected-shortcut"))

        video3_wrapper = page.locator('.thumbnail-wrapper', has_text='video3.mp4')
        # This one should have no special class
        await expect(video3_wrapper).not_to_have_class(re.compile(r"selected-"))


        # Take a screenshot to confirm visually
        await page.screenshot(path="verify_css_fix_screenshot.png")
        print("Screenshot saved as verify_css_fix_screenshot.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
