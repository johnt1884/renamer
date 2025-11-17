import asyncio
import os
import re
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        file_path = f"file://{os.getcwd()}/renamer.html"
        await page.goto(file_path)

        # CRITICAL: Disable the page's own onload handler to prevent race conditions.
        await page.evaluate('window.onload = null;')

        # --- Test 1: Verify Popout Menus ---
        print("--- Verifying Popout Menus ---")
        await page.evaluate("""async () => {
            window.initializeUI();
            const recentDirs = [
                { name: 'Dir 1', handle: {} }, { name: 'Dir 2', handle: {} },
            ];
            await window.setDb('recentDirectories', recentDirs);
            await window.loadRecentDirectories();
        }""")
        await page.click("#cog-btn")

        print("Opening Recent Directories menu...")
        await page.click("#recent-directories-dropdown a")
        await expect(page.locator("#recent-directories-list")).to_be_visible()
        await page.screenshot(path="verification/popout_recent_dirs_final.png")
        print("Saved popout_recent_dirs_final.png")

        print("Opening Thumbnails menu...")
        await page.click("#thumbnails-menu a")
        await expect(page.locator("#thumbnails-menu-list")).to_be_visible()
        await page.screenshot(path="verification/popout_thumbnails_final.png")
        print("Saved popout_thumbnails_final.png")
        await page.click("#cog-btn")

        # --- Test 2: Edit Mode Pre-selection and Dirty Flag ---
        print("\\n--- Verifying Edit Mode Pre-selection and Dirty Flag ---")
        await page.evaluate("""async () => {
            const rootThumbnailsDir = new window.MockDirectoryHandle('Thumbnails', new Map([
                ['video1.jpg', new window.MockFileHandle('video1.jpg')], ['video2.jpg', new window.MockFileHandle('video2.jpg')],
                ['video3.jpg', new window.MockFileHandle('video3.jpg')], ['video4.jpg', new window.MockFileHandle('video4.jpg')]
            ]));
            const editThumbnailsDir = new window.MockDirectoryHandle('Edit Thumbnails', new Map([
                ['video1_1.jpg', new window.MockFileHandle('video1_1.jpg')], ['video2_1.jpg', new window.MockFileHandle('video2_1.jpg')],
                ['video3_1.jpg', new window.MockFileHandle('video3_1.jpg')], ['video4_1.jpg', new window.MockFileHandle('video4_1.jpg')]
            ]));
            const landscapeDir = new window.MockDirectoryHandle('Landscape', new Map([['video2.mp4', new window.MockFileHandle('video2.mp4')]]));
            const editDir = new window.MockDirectoryHandle('Edit', new Map([['video3.mp4', new window.MockFileHandle('video3.mp4')]]));
            const scDir = new window.MockDirectoryHandle('sc', new Map([['video4.mp4.lnk', new window.MockFileHandle('video4.mp4.lnk')]]));
            const rootDir = new window.MockDirectoryHandle('verification-edit-mode', new Map([
                ['video1.mp4', new window.MockFileHandle('video1.mp4')], ['video3.mp4', new window.MockFileHandle('video3.mp4')],
                ['video4.mp4', new window.MockFileHandle('video4.mp4')], ['Thumbnails', rootThumbnailsDir],
                ['Edit Thumbnails', editThumbnailsDir], ['Landscape', landscapeDir], ['Edit', editDir], ['sc', scDir]
            ]));
            window.allVideoFiles = [
                { name: 'video1.mp4', customPath: '', lastModified: Date.now() }, { name: 'video2.mp4', customPath: 'Landscape', lastModified: Date.now() },
                { name: 'video3.mp4', customPath: 'Edit', lastModified: Date.now() }, { name: 'video4.mp4', customPath: '', lastModified: Date.now() },
            ];
            await window.processDirectory(rootDir);
        }""")

        await page.click("#cog-btn")
        await page.click("#edit-mode-btn")

        await page.wait_for_selector(".landscape-row")
        await expect(page.locator(".landscape-row[data-video-name='video2']")).to_have_attribute('class', re.compile(r'selected-landscape'))
        await expect(page.locator(".landscape-row[data-video-name='video3']")).to_have_attribute('class', re.compile(r'selected-edit'))
        await expect(page.locator(".landscape-row[data-video-name='video4']")).to_have_attribute('class', re.compile(r'selected-shortcut'))

        print("Taking screenshot of pre-selections...")
        await page.screenshot(path="verification/edit_mode_preselection_final.png")
        print("Saved edit_mode_preselection_final.png")

        print("Testing dirty flag...")

        # Manually set the dirty flag
        await page.evaluate("localStorage.setItem('renamer-directory-is-dirty-verification-edit-mode', 'true')")
        print("Dirty flag manually set.")

        dialog_message = None
        async def handle_dialog(dialog):
            nonlocal dialog_message
            dialog_message = dialog.message
            await dialog.dismiss()
        page.on("dialog", handle_dialog)

        # Click the button again (now in 'On' state) to trigger the check
        await page.click("#edit-mode-btn")
        await page.wait_for_timeout(500)

        assert "The directory has been modified" in (dialog_message or ""), "Confirmation dialog did not appear!"
        print("Confirmation dialog test passed.")

        await browser.close()
        print("\\nVerification script completed successfully!")

if __name__ == '__main__':
    asyncio.run(main())
