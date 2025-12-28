
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
            const createMockFile = (name, lastModified) => {
                const base64Gif = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                const byteCharacters = atob(base64Gif);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {type: 'image/gif'});
                return new File([blob], name, { type: 'image/gif', lastModified });
            };

            window.MockFileHandle = class MockFileHandle {
                constructor(name, lastModified) {
                    this.name = name;
                    this.kind = 'file';
                    this.lastModified = lastModified;
                }
                async getFile() {
                    return createMockFile(this.name, this.lastModified);
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

            const LATEST_SHORTCUT_TIME = 1704067200000; // Jan 1, 2024

            window.currentDirHandle = new window.MockDirectoryHandle('root', {
                'Project 1': new window.MockDirectoryHandle('Project 1', {
                    'sc': new window.MockDirectoryHandle('sc', {
                        'shortcut1.lnk': new window.MockFileHandle('shortcut1.lnk', LATEST_SHORTCUT_TIME)
                    }),
                    'Edit Thumbnails': new window.MockDirectoryHandle('Edit Thumbnails', {
                        // Scenario 1: Video is NEW, thumbnail is NEW -> SHOULD BE SHOWN
                        'video_new_thumb_new_1.jpg': new window.MockFileHandle('video_new_thumb_new_1.jpg', LATEST_SHORTCUT_TIME + 1000),
                        // Scenario 2: Video is OLD, thumbnail is NEW -> SHOULD BE HIDDEN
                        'video_old_thumb_new_1.jpg': new window.MockFileHandle('video_old_thumb_new_1.jpg', LATEST_SHORTCUT_TIME + 1000),
                        // Scenario 3: Video is NEW, thumbnail is OLD -> SHOULD BE SHOWN
                        'video_new_thumb_old_1.jpg': new window.MockFileHandle('video_new_thumb_old_1.jpg', LATEST_SHORTCUT_TIME - 1000),
                         // Scenario 4: Video is OLD, thumbnail is OLD -> SHOULD BE HIDDEN
                        'video_old_thumb_old_1.jpg': new window.MockFileHandle('video_old_thumb_old_1.jpg', LATEST_SHORTCUT_TIME - 1000),
                    }),
                    'video_new_thumb_new.mp4': new window.MockFileHandle('video_new_thumb_new.mp4', LATEST_SHORTCUT_TIME + 1000),
                    'video_old_thumb_new.mp4': new window.MockFileHandle('video_old_thumb_new.mp4', LATEST_SHORTCUT_TIME - 1000),
                    'video_new_thumb_old.mp4': new window.MockFileHandle('video_new_thumb_old.mp4', LATEST_SHORTCUT_TIME + 1000),
                    'video_old_thumb_old.mp4': new window.MockFileHandle('video_old_thumb_old.mp4', LATEST_SHORTCUT_TIME - 1000),
                })
            });

            await window.renderShortcutMode();
        })();
        """)


        await expect(page.locator(".project-header")).to_have_count(1)
        # We expect only the two thumbnails corresponding to NEW videos to be visible
        await expect(page.locator(".thumbnail")).to_have_count(2)

        # Verify that the correct thumbnails are visible
        await expect(page.locator('img[data-file-name="video_new_thumb_new_1.jpg"]')).to_be_visible()
        await expect(page.locator('img[data-file-name="video_new_thumb_old_1.jpg"]')).to_be_visible()

        # Verify that the incorrect thumbnails are hidden
        await expect(page.locator('img[data-file-name="video_old_thumb_new_1.jpg"]')).to_have_count(0)
        await expect(page.locator('img[data-file-name="video_old_thumb_old_1.jpg"]')).to_have_count(0)

        print("✅ Date filtering rigorously verified successfully.")

        await page.screenshot(path="verification_screenshot.png")
        print("📸 Screenshot captured.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
