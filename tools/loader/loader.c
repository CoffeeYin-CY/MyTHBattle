#include <stdlib.h>
#include <tchar.h>
#include <windows.h>

LPCTSTR ERROR_PROMPT =
    _T("��Ϸ�����ˣ�\n")
    _T("\n")
    _T("���󱨸�Ӧ���Ѿ��Զ������ˣ������ĵȵȰɡ���\n")
    _T("�����Ϸ��ͣ�ı�������ȷ���ǲ����Կ�������������⣬���Ÿ���һ���Կ���������\n")
    _T("nVIDIA����http://www.nvidia.cn/Download/index.aspx?lang=cn\n")
    _T("AMD����http://support.amd.com/us/gpudownload/Pages/index.aspx\n")
    _T("\n")
    _T("�����ǰ��������Ϸ����ͻȻ�治���ˣ���ִ��һ����ϷĿ¼�е�update.bat��\n")
    _T("Ȼ���ٴ���Ϸ��\n")
    _T("\n")
    _T("��Ȼ���еĻ�����ȥhttp://www.thbattle.net������Թ����")
;

int execute(LPCTSTR app, LPCTSTR cargs)
{
    PROCESS_INFORMATION pinfo;
    STARTUPINFO sinfo = { sizeof(sinfo) };
    BOOL rst;
    DWORD exitcode = 1;

    LPTSTR args = _tcsdup(cargs);
    rst = CreateProcess(app, args, NULL, NULL, FALSE, 0, NULL, NULL, &sinfo, &pinfo);
    free(args);

    if(!rst) {
        return 1;
    }
    CloseHandle(pinfo.hThread);
    WaitForSingleObject(pinfo.hProcess, INFINITE);
    GetExitCodeProcess(pinfo.hProcess, &exitcode);
    CloseHandle(pinfo.hProcess);
    return exitcode;
}


int __stdcall _tWinMain(HINSTANCE hInstance,
                     HINSTANCE hPrevInstance,
                     LPTSTR    lpCmdLine,
                     int       nCmdShow)
{
    int rst;
    rst = execute(_T("Python27\\pythonw.exe"), _T("pythonw.exe"));
    if(rst) {
        // failed, install vcredist
        execute(_T("Python27\\vcredist_x86.exe"), _T("vcredist_x86.exe"));
    }
    rst = execute(_T("Python27\\pythonw.exe"), _T("pythonw.exe src\\start_client.py"));
    if(rst) {
        ShellExecute(0, _T("open"), _T("update.bat"), NULL, NULL, 0);
        MessageBox(NULL, ERROR_PROMPT, _T("��Ϸ������"), MB_ICONINFORMATION);
    }
    return 0;
}