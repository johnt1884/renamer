
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
            // This class now simulates reading text content for scdate.txt
            window.MockFileHandle = class MockFileHandle {
                constructor(name, lastModified, textContent = null) {
                    this.name = name;
                    this.kind = 'file';
                    this.lastModified = lastModified;
                    this._textContent = textContent;
                }
                async getFile() {
                    let blob;
                    if (this._textContent !== null) {
                        blob = new Blob([this._textContent], {type: 'text/plain'});
                    } else {
                        const base64Gif = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                        const byteCharacters = atob(base64Gif);
                        const byteNumbers = new Array(byteCharacters.length);
                        for (let i = 0; i < byteCharacters.length; i++) {
                            byteNumbers[i] = byteCharacters.charCodeAt(i);
                        }
                        const byteArray = new Uint8Array(byteNumbers);
                        blob = new Blob([byteArray], {type: 'image/gif'});
                    }
                    return new File([blob], this.name, { type: blob.type, lastModified: this.lastModified });
                }
            }

            window.MockDirectoryHandle = class MockDirectoryHandle {
                constructor(name, entries = {}) {
                    this.name = name;
                    this.kind = 'directory';
                    this._entries = new Map(Object.entries(entries));
                }
                async getFileHandle(name) {
                     const entry = this._entries.get(name);
                    if (entry && entry.kind === 'file') {
                        return entry;
                    }
                    throw new Error(`File not found: ${name}`);
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

            const LATEST_SHORTCUT_TIME = 1704153600000; // Jan 2, 2024 00:00:00
            const DATE_STRING = '2024-01-02 00:00';

            window.currentDirHandle = new window.MockDirectoryHandle('root', {
                'Project 1': new window.MockDirectoryHandle('Project 1', {
                    'scdate.txt': new window.MockFileHandle('scdate.txt', LATEST_SHORTCUT_TIME, DATE_STRING),
                    'Edit Thumbnails': new window.MockDirectoryHandle('Edit Thumbnails', {
                        'video_new_thumb_1.jpg': new window.MockFileHandle('video_new_thumb_1.jpg', LATEST_SHORTCUT_TIME + 1000), // Should be visible
                        'video_old_thumb_1.jpg': new window.MockFileHandle('video_old_thumb_1.jpg', LATEST_SHORTCUT_TIME - 1000), // Should be hidden
                    }),
                    'video_new.mp4': new window.MockFileHandle('video_new.mp4', LATEST_SHORTCUT_TIME - 2000), // Video date is irrelevant now
                    'video_old.mp4': new window.MockFileHandle('video_old.mp4', LATEST_SHORTCUT_TIME - 2000),
                })
            });

            await window.renderShortcutMode();
        })();
        """)


        await expect(page.locator(".project-header")).to_have_count(1)
        await expect(page.locator(".thumbnail")).to_have_count(1)

        await expect(page.locator('img[data-file-name="video_new_thumb_1.jpg"]')).to_be_visible()
        await expect(page.locator('img[data-file-name="video_old_thumb_1.jpg"]')).to_have_count(0)

        print("✅ Date filtering with scdate.txt rigorously verified successfully.")

        await page.locator("#show-dates-checkbox").check()

        header_date_locator = page.locator(".project-header .date-info")
        await expect(header_date_locator).to_be_visible()
        header_date_text = await header_date_locator.inner_text()
        assert "1/2/2024" in header_date_text
        assert "12:00:00 AM" in header_date_text
        print("✅ Header date format verified.")

        await page.screenshot(path="verification_screenshot.png")
        print("📸 Screenshot captured.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
