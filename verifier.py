
import asyncio
import json
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

            window.currentDirHandle = new window.MockDirectoryHandle('root', {
                'Project 1': new window.MockDirectoryHandle('Project 1', {
                    'sc': new window.MockDirectoryHandle('sc', {
                        'shortcut1.lnk': new window.MockFileHandle('shortcut1.lnk', 1704067200000)
                    }),
                    'Edit Thumbnails': new window.MockDirectoryHandle('Edit Thumbnails', {
                        'video1_thumb_old.jpg': new window.MockFileHandle('video1_thumb_old.jpg', 1704067100000),
                        'video1_thumb_new.jpg': new window.MockFileHandle('video1_thumb_new.jpg', 1704067300000)
                    }),
                    'video1.mp4': new window.MockFileHandle('video1.mp4', 1704067100000)
                }),
                'Project 2': new window.MockDirectoryHandle('Project 2', {
                    'sc': new window.MockDirectoryHandle('sc', {
                        'shortcut2.lnk': new window.MockFileHandle('shortcut2.lnk', 1706745600000)
                    }),
                    'Edit Thumbnails': new window.MockDirectoryHandle('Edit Thumbnails', {
                        'video2_thumb_old.jpg': new window.MockFileHandle('video2_thumb_old.jpg', 1706745500000),
                        'video2_thumb_new.jpg': new window.MockFileHandle('video2_thumb_new.jpg', 1706745700000)
                    }),
                    'video2.mp4': new window.MockFileHandle('video2.mp4', 1706745500000)
                })
            });

            await window.renderShortcutMode();
        })();
        """)


        await expect(page.locator(".project-header")).to_have_count(2)
        await expect(page.locator(".thumbnail")).to_have_count(2)
        await expect(page.locator('img[data-file-name="video1_thumb_new.jpg"]')).to_be_visible()
        await expect(page.locator('img[data-file-name="video2_thumb_new.jpg"]')).to_be_visible()
        await expect(page.locator('img[data-file-name="video1_thumb_old.jpg"]')).to_have_count(0)
        await expect(page.locator('img[data-file-name="video2_thumb_old.jpg"]')).to_have_count(0)
        print("✅ Date filtering verified successfully.")

        thumb_selector = 'img[data-file-name="video1_thumb_new.jpg"]'
        thumb = page.locator(thumb_selector)
        initial_box = await thumb.bounding_box()
        initial_width = initial_box['width']
        print(f"Initial thumbnail width: {initial_width}")

        await page.locator("#size-selector").select_option("0.5")
        await page.evaluate("window.layoutLandscapeThumbnails()")
        await page.wait_for_function(f"() => {{ const thumb = document.querySelector('{thumb_selector}'); return thumb && thumb.getBoundingClientRect().width !== {initial_width}; }}")
        final_box = await thumb.bounding_box()
        final_width = final_box['width']
        print(f"Final thumbnail width: {final_width}")

        if final_width < initial_width:
             print("✅ Size selector verified successfully.")
        else:
            print(f"❌ Size selector verification failed. Width did not decrease as expected.")

        await page.screenshot(path="verification_screenshot.png")
        print("📸 Screenshot captured.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
