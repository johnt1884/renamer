
import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))

        await page.goto(f"file:///app/shortcuts.html")

        await page.evaluate("""
        (async () => {
            window.MockFileHandle = class MockFileHandle {
                constructor(name, lastModified) {
                    this.name = name;
                    this.kind = 'file';
                    this.lastModified = lastModified;
                }
                async getFile() {
                    const base64Gif = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                    const byteCharacters = atob(base64Gif);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], {type: 'image/gif'});
                    return new File([blob], this.name, { type: 'image/gif', lastModified });
                }
            }

            window.MockDirectoryHandle = class MockDirectoryHandle {
                constructor(name, entries = {}) {
                    this.name = name;
                    this.kind = 'directory';
                    this._entries = new Map(Object.entries(entries));
                }
                async getDirectoryHandle(name) {
                    const entry = this._entries.get(name);
                    if (entry && entry.kind === 'directory') {
                        return entry;
                    }
                    throw new Error(`Directory not found: ${name}`);
                }
                async *values() {
                    for (const value of this._entries.values()) {
                        yield value;
                    }
                }
            }

            const LATEST_SHORTCUT_TIME = 1704067200000; // Jan 1, 2024 00:00:00

            window.currentDirHandle = new window.MockDirectoryHandle('root', {
                'Project 1': new window.MockDirectoryHandle('Project 1', {
                    'sc': new window.MockDirectoryHandle('sc', {
                        'shortcut1.lnk': new window.MockFileHandle('shortcut1.lnk', LATEST_SHORTCUT_TIME)
                    }),
                    'Edit Thumbnails': new window.MockDirectoryHandle('Edit Thumbnails', {
                        'video_new_thumb_1.jpg': new window.MockFileHandle('video_new_thumb_1.jpg', LATEST_SHORTCUT_TIME + 1000), // Should be visible
                        'video_old_thumb_1.jpg': new window.MockFileHandle('video_old_thumb_1.jpg', LATEST_SHORTCUT_TIME - 1000), // Should be hidden
                    }),
                    'video_new.mp4': new window.MockFileHandle('video_new.mp4', LATEST_SHORTCUT_TIME + 1000),
                    'video_old.mp4': new window.MockFileHandle('video_old.mp4', LATEST_SHORTCUT_TIME - 1000),
                })
            });

            await window.renderShortcutMode();
        })();
        """)


        await expect(page.locator(".project-header")).to_have_count(1)
        await expect(page.locator(".thumbnail")).to_have_count(1)

        # Verify that the correct thumbnail is visible
        await expect(page.locator('img[data-file-name="video_new_thumb_1.jpg"]')).to_be_visible()

        # Verify that the old thumbnail is hidden
        await expect(page.locator('img[data-file-name="video_old_thumb_1.jpg"]')).to_have_count(0)

        print("✅ Date filtering rigorously verified successfully.")

        await page.locator("#show-dates-checkbox").check()

        header_date_locator = page.locator(".project-header .date-info")
        await expect(header_date_locator).to_be_visible()
        header_date_text = await header_date_locator.inner_text()
        assert "1/1/2024" in header_date_text
        assert "12:00:00 AM" in header_date_text
        print("✅ Header date format verified.")

        row_date_locator = page.locator(".landscape-row .date-info")
        await expect(row_date_locator).to_be_visible()
        row_date_text = await row_date_locator.inner_text()
        assert "1/1/2024" in row_date_text
        assert "12:00:01 AM" in row_date_text
        print("✅ Row date format verified.")

        await page.screenshot(path="verification_screenshot.png")
        print("📸 Screenshot captured.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
