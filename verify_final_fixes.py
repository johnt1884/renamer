
import asyncio
import os
import re
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))

        file_path = os.path.abspath('renamer.html')
        await page.goto(f"file://{file_path}")
        await page.wait_for_load_state('load')

        await page.evaluate("""
            () => {
                class MockFileHandle {
                    constructor(name, lastModified = Date.now()) {
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
                        return new File([blob], this.name, { type: 'image/gif', lastModified: this.lastModified });
                    }
                }

                class MockDirectoryHandle {
                    constructor(name, entries) {
                        this.name = name;
                        this.kind = 'directory';
                        this._entries = entries;
                    }
                    async getDirectoryHandle(name) {
                        const entry = this._entries.get(name);
                        if (entry && entry.kind === 'directory') return entry;
                        throw new DOMException('NotFoundError');
                    }
                    async *values() {
                        for (const value of this._entries.values()) yield value;
                    }
                }

                const thumbnailsDir = new MockDirectoryHandle('Thumbnails', new Map([
                    ['video1.jpg', new MockFileHandle('video1.jpg', 1731859200000)],
                    ['video2.jpg', new MockFileHandle('video2.jpg', 1731862800000)],
                    ['video3.jpg', new MockFileHandle('video3.jpg', 1731855600000)]
                ]));

                const editThumbnailsDir = new MockDirectoryHandle('Edit Thumbnails', new Map([
                    ['video1_1.jpg', new MockFileHandle('video1_1.jpg')],
                    ['video2_1.jpg', new MockFileHandle('video2_1.jpg')],
                    ['video3_1.jpg', new MockFileHandle('video3_1.jpg')]
                ]));

                const landscapeDir = new MockDirectoryHandle('Landscape', new Map([
                    ['video1.mp4', new MockFileHandle('video1.mp4')]
                ]));

                const scDir = new MockDirectoryHandle('sc', new Map([
                    ['video2.mp4.lnk', new MockFileHandle('video2.mp4.lnk')]
                ]));

                const rootDir = new MockDirectoryHandle('test-dir', new Map([
                    ['video1.mp4', new MockFileHandle('video1.mp4', 1731859200000)],
                    ['video2.mp4', new MockFileHandle('video2.mp4', 1731862800000)],
                    ['video3.mp4', new MockFileHandle('video3.mp4', 1731855600000)],
                    ['Thumbnails', thumbnailsDir],
                    ['Edit Thumbnails', editThumbnailsDir],
                    ['Landscape', landscapeDir],
                    ['sc', scDir]
                ]));

                window.showDirectoryPicker = async () => rootDir;
            }
        """)

        await page.click('#load-directory-btn')

        await expect(page.locator('.thumbnail-wrapper')).to_have_count(3)
        print("Initial thumbnails loaded successfully.")

        # --- Test date sorting (newest first) ---
        await page.select_option('#sort-selector', 'date-newest')
        await page.wait_for_timeout(500) # Pragmatic delay to allow DOM to update
        await expect(page.locator('.thumbnail-wrapper .thumbnail-name').first).to_have_text('video2.jpg')
        print("Sort by date (newest) verified.")

        # --- Test date sorting (oldest first) ---
        await page.select_option('#sort-selector', 'date-oldest')
        await page.wait_for_timeout(500) # Pragmatic delay
        await expect(page.locator('.thumbnail-wrapper .thumbnail-name').first).to_have_text('video3.jpg')
        print("Sort by date (oldest) verified.")


        # Correctly enter Edit Mode by clicking the cog, then the edit mode button
        await page.click('#cog-btn')
        edit_mode_button = page.locator('#edit-mode-btn')
        await expect(edit_mode_button).to_be_visible()
        await edit_mode_button.click()

        await expect(page.locator('.landscape-row')).to_have_count(3)
        print("Entered Edit Mode successfully.")

        video1_row = page.locator('.landscape-row[data-video-name="video1"]')
        await expect(video1_row).to_have_class(re.compile(r"selected-landscape"))
        print("Verified: video1 is pre-selected for Landscape.")

        video2_row = page.locator('.landscape-row[data-video-name="video2"]')
        await expect(video2_row).to_have_class(re.compile(r"selected-shortcut"))
        print("Verified: video2 is pre-selected for Shortcut.")

        video3_row = page.locator('.landscape-row[data-video-name="video3"]')
        await expect(video3_row).not_to_have_class(re.compile(r"selected-"))
        print("Verified: video3 has no pre-selection.")

        # Test the differential script generation
        await page.click('#landscape-btn')
        await video1_row.click()
        await expect(video1_row).not_to_have_class(re.compile(r"selected-landscape"))
        print("Deselected video1 from Landscape.")

        await page.click('#edit-btn')
        await video3_row.click()
        await expect(video3_row).to_have_class(re.compile(r"selected-edit"))
        print("Selected video3 for Edit.")

        await page.click('#cog-btn')
        await page.click('#generate-edit-bat-btn')

        script_content = await page.input_value('#final-landscape-batch-script')

        assert 'Move-Item -LiteralPath "Landscape\\video1.mp4" -Destination "."' in script_content
        print("Verified: Script contains command to REMOVE video1 from Landscape.")

        assert 'Move-Item -LiteralPath "video3.mp4" -Destination "Edit"' in script_content
        print("Verified: Script contains command to ADD video3 to Edit.")

        assert 'video2.mp4' not in script_content
        print("Verified: Script does not contain unchanged actions for video2.")

        await page.screenshot(path="verify_final_fixes.png")
        print("Screenshot saved as verify_final_fixes.png")

        await browser.close()
        print("Verification successful!")

if __name__ == "__main__":
    asyncio.run(main())
