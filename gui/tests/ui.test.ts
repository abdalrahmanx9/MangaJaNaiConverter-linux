import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';

// Read HTML template
const html = fs.readFileSync(path.resolve(__dirname, '../index.html'), 'utf-8');

// Mock Tauri API before main.ts imports it
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (cmd, args) => {
    if (cmd === 'check_env_exists') return true;
    if (cmd === 'get_gpu_info') return { name: 'Mock GPU', vram_mb: 8192 };
    if (cmd === 'get_available_models') return ['model1.pth', 'model2.safetensors'];
    if (cmd === 'save_settings') return '/tmp/mock-settings.json';
    if (cmd === 'start_upscale') return true;
    if (cmd === 'read_text_file') {
        const mockJson = { workflow_name: "Imported Mock Workflow" };
        return JSON.stringify(mockJson);
    }
    if (cmd === 'save_workflow') return '/tmp/exported.json';
    return null;
  }),
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(async ({ directory }) => {
    return directory ? '/mock/folder/path' : '/mock/file/path.cbz';
  }),
}));

vi.mock('@tauri-apps/plugin-opener', () => ({
  openPath: vi.fn(async (p) => true),
}));

describe('Tauri GUI Interaction Tests', () => {
  let mainModule: any;

  beforeEach(async () => {
    document.body.innerHTML = html;
    vi.resetModules();
    mainModule = await import('../src/main.ts');
    await mainModule.init();
    await new Promise(r => setTimeout(r, 100)); // Allow init async tasks
  });

  it('should toggle between Single File and Batch Folder tabs', async () => {
    const singleTabBtn = document.querySelector('button[data-tab="single-file"]') as HTMLButtonElement;
    const batchTabBtn = document.querySelector('button[data-tab="batch-folder"]') as HTMLButtonElement;

    batchTabBtn.click();
    expect(mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].selected_tab_index).toBe(1);

    singleTabBtn.click();
    expect(mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].selected_tab_index).toBe(0);
  });

  it('should update Output Formats correctly', async () => {
    const formatBtns = document.querySelectorAll('#format-toggle-group .toggle-btn');
    const avifBtn = Array.from(formatBtns).find(b => b.getAttribute('data-format') === 'avif') as HTMLButtonElement;
    avifBtn.click();
    const wf = mainModule.appSettings.workflows[mainModule.currentWorkflowIndex];
    expect(wf.avif_selected).toBe(true);
    expect(wf.webp_selected).toBe(false);
  });

  it('should toggle Advanced Settings visibility', async () => {
    const showAdvancedChk = document.getElementById('show-advanced-settings-chk') as HTMLInputElement;
    const advancedSection = document.getElementById('advanced-settings-section') as HTMLElement;
    
    // Unchecked by default
    expect(mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].show_advanced_settings).toBe(false);
    expect(advancedSection.style.display).toBe('none');

    // Check
    showAdvancedChk.click(); 
    expect(mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].show_advanced_settings).toBe(true);
    expect(advancedSection.style.display).toBe('block');
  });

  it('should interact with Chain inputs (Resize Factor, Model, Tile Size)', async () => {
    const wf = mainModule.appSettings.workflows[mainModule.currentWorkflowIndex];
    
    const rfInput = document.querySelector('.chain-rf') as HTMLInputElement;
    rfInput.value = '150';
    rfInput.dispatchEvent(new Event('change'));
    expect(wf.chains[0].resize_factor_before_upscale).toBe(150);

    const tileSelect = document.querySelector('.chain-tile') as HTMLSelectElement;
    tileSelect.value = '256';
    tileSelect.dispatchEvent(new Event('change'));
    expect(wf.chains[0].model_tile_size).toBe('256');

    const openModelsBtn = document.querySelector('.chain-open-models-btn') as HTMLButtonElement;
    openModelsBtn.click();
    // It should invoke the backend open_folder command via Tauri
    const { invoke } = await import('@tauri-apps/api/core');
    expect(invoke).toHaveBeenCalledWith('open_folder', { path: expect.stringContaining('backend/models') });
  });

  it('should trigger upscale process and disable buttons', async () => {
    const upscaleBtn = document.getElementById('upscale-btn') as HTMLButtonElement;
    const cancelBtn = document.getElementById('cancel-btn') as HTMLButtonElement;
    mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].input_file_path = "test.zip";
    mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].output_folder_path = "/mock/output";
    mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].selected_tab_index = 0;
    mainModule.appSettings.workflows[mainModule.currentWorkflowIndex].chains.forEach((c: any) => c.model_file_path = 'model1.pth');
    upscaleBtn.disabled = false;
    upscaleBtn.click();
    await new Promise(r => setTimeout(r, 300));
    expect(upscaleBtn.disabled).toBe(true);
    expect(cancelBtn.disabled).toBe(false);
  });
  
  it('should toggle between dark and light theme', async () => {
    const toggleBtn = document.getElementById('theme-toggle-btn') as HTMLButtonElement;

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    toggleBtn.click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    toggleBtn.click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('should import a new custom workflow and display it in sidebar', async () => {
    const importBtn = document.getElementById('import-workflow-btn') as HTMLButtonElement;
    const initialWfCount = mainModule.appSettings.workflows.length;
    
    importBtn.click();
    await new Promise(r => setTimeout(r, 50));
    
    // Workflow was pushed
    expect(mainModule.appSettings.workflows.length).toBe(initialWfCount + 1);
    expect(mainModule.appSettings.workflows[initialWfCount].workflow_name).toBe("Imported Mock Workflow");
    expect(mainModule.currentWorkflowIndex).toBe(initialWfCount);

    // Sidebar should have the new workflow
    const container = document.getElementById('custom-workflows-container')!;
    const sidebarBtns = container.querySelectorAll('.nav-btn');
    expect(sidebarBtns.length).toBe(1); // 1 custom workflow + 1 default
    expect(sidebarBtns[0].textContent).toContain("Imported Mock Workflow");
  });
});
