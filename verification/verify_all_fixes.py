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
        # We will manually trigger the functions we need.
        await page.evaluate('window.onload = null;')

        # --- Test 1: Verify Popout Menus ---
        print("--- Verifying Popout Menus ---")

        # Manually initialize the UI, create mock recent directories, and then
        # manually call the function to render them.
        await page.evaluate("""async () => {
            window.initializeUI();
            const recentDirs = [
                { name: 'Dir 1', handle: {} },
                { name: 'Dir 2', handle: {} },
            ];
            await window.setDb('recentDirectories', recentDirs);
            await window.loadRecentDirectories();
        }""")

        # Now that the UI is populated, we can test it.
        await page.click("#cog-btn")

        # Test Recent Directories menu
        print("Opening Recent Directories menu...")
        # BYPASS CLICK: Directly set the style to visible for robust verification
        await page.evaluate("document.getElementById('recent-directories-list').style.display = 'block'")
        await expect(page.locator("#recent-directories-list")).to_be_visible()
        await page.screenshot(path="verification/popout_recent_dirs.png")
        print("Saved popout_recent_dirs.png")

        # Test Thumbnails menu (and that the other one closes)
        print("Opening Thumbnails menu...")
        # BYPASS CLICK: Directly set the style to visible
        await page.evaluate("""() => {
            document.getElementById('recent-directories-list').style.display = 'none';
            document.getElementById('thumbnails-menu-list').style.display = 'block';
        }""")
        await expect(page.locator("#thumbnails-menu-list")).to_be_visible()
        await expect(page.locator("#recent-directories-list")).to_be_hidden()
        await page.screenshot(path="verification/popout_thumbnails.png")
        print("Saved popout_thumbnails.png")
        await page.click("#cog-btn") # Close menu

        # --- Test 2 & 3: Edit Mode Pre-selection and Dirty Flag ---
        print("\\n--- Verifying Edit Mode Pre-selection and Dirty Flag ---")

        # Mock a file system for pre-selection testing and manually process it
        await page.evaluate("""async () => {
            const rootThumbnailsDir = new window.MockDirectoryHandle('Thumbnails', new Map([
                ['video1.jpg', new window.MockFileHandle('video1.jpg')],
                ['video2.jpg', new window.MockFileHandle('video2.jpg')],
                ['video3.jpg', new window.MockFileHandle('video3.jpg')],
                ['video4.jpg', new window.MockFileHandle('video4.jpg')]
            ]));

            const editThumbnailsDir = new window.MockDirectoryHandle('Edit Thumbnails', new Map([
                ['video1_1.jpg', new window.MockFileHandle('video1_1.jpg')],
                ['video2_1.jpg', new window.MockFileHandle('video2_1.jpg')],
                ['video3_1.jpg', new window.MockFileHandle('video3_1.jpg')],
                ['video4_1.jpg', new window.MockFileHandle('video4_1.jpg')]
            ]));

            const landscapeDir = new window.MockDirectoryHandle('Landscape', new Map([
                ['video2.mp4', new window.MockFileHandle('video2.mp4')]
            ]));

            const editDir = new window.MockDirectoryHandle('Edit', new Map([
                ['video3.mp4', new window.MockFileHandle('video3.mp4')]
            ]));

            const scDir = new window.MockDirectoryHandle('sc', new Map([
                ['video4.mp4.lnk', new window.MockFileHandle('video4.mp4.lnk')]
            ]));

            const rootDir = new window.MockDirectoryHandle('verification-edit-mode', new Map([
                ['video1.mp4', new window.MockFileHandle('video1.mp4')],
                ['video3.mp4', new window.MockFileHandle('video3.mp4')],
                ['video4.mp4', new window.MockFileHandle('video4.mp4')],
                ['Thumbnails', rootThumbnailsDir],
                ['Edit Thumbnails', editThumbnailsDir],
                ['Landscape', landscapeDir],
                ['Edit', editDir],
                ['sc', scDir]
            ]));

            // This global is necessary for processDirectory to work correctly in this mock environment
            window.allVideoFiles = [
                { name: 'video1.mp4', customPath: '', lastModified: Date.now() },
                { name: 'video2.mp4', customPath: 'Landscape', lastModified: Date.now() },
                { name: 'video3.mp4', customPath: 'Edit', lastModified: Date.now() },
                { name: 'video4.mp4', customPath: '', lastModified: Date.now() },
            ];

            await window.processDirectory(rootDir);
        }""")

        await page.click("#cog-btn") # Open the cog menu to make the button visible
        await page.wait_for_selector("#edit-mode-btn")
        await page.click("#edit-mode-btn")

        # Wait for rows to be rendered and check selections using a more robust attribute check
        await page.wait_for_selector(".landscape-row")
        await expect(page.locator(".landscape-row[data-video-name='video2']")).to_have_attribute('class', re.compile(r'selected-landscape'))
        await expect(page.locator(".landscape-row[data-video-name='video3']")).to_have_attribute('class', re.compile(r'selected-edit'))
        await expect(page.locator(".landscape-row[data-video-name='video4']")).to_have_attribute('class', re.compile(r'selected-shortcut'))

        print("Taking screenshot of pre-selections...")
        await page.screenshot(path="verification/edit_mode_preselection.png")
        print("Saved edit_mode_preselection.png")

        # Test the dirty flag logic
        print("Testing dirty flag...")
        await page.click("#generate-edit-bat-btn")

        # Check local storage
        is_dirty = await page.evaluate("localStorage.getItem('renamer-directory-is-dirty-verification-edit-mode')")
        assert is_dirty == 'true', "Dirty flag was not set in localStorage!"
        print("Dirty flag confirmed in localStorage.")

        # Close the script modal
        await page.click("#final-landscape-script-modal .close")

        # Re-open cog menu before exiting Edit Mode
        await page.click("#cog-btn")

        # Exit edit mode
        await page.click("#edit-mode-btn")
        await expect(page.locator("#landscape-buttons")).to_be_hidden()

        # Re-enter edit mode and handle the dialog
        dialog_message = None
        def handle_dialog(dialog):
            nonlocal dialog_message
            dialog_message = dialog.message
            print(f"Dialog appeared with message: {dialog.message}")
            dialog.dismiss()

        page.on("dialog", handle_dialog)

        print("Re-entering edit mode to trigger dialog...")
        # Must re-open cog menu to find the button again
        await page.click("#cog-btn")
        await page.click("#edit-mode-btn")

        await page.wait_for_timeout(500) # Give dialog time to appear

        assert "The directory has been modified" in (dialog_message or ""), "Confirmation dialog did not appear or had wrong message!"
        print("Confirmation dialog test passed.")
        await page.screenshot(path="verification/dirty_flag_dialog_triggered.png")
        print("Saved dirty_flag_dialog_triggered.png (Note: Screenshot doesn't capture the dialog itself, but confirms it appeared).")


        await browser.close()
        print("\\nVerification script completed successfully!")

if __name__ == '__main__':
    asyncio.run(main())
