#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

const char *ERROR_PROMPT = (
    "��Ϸ�����ˣ�\n"
    "\n"
    "���󱨸�Ӧ���Ѿ��Զ������ˣ������ĵȵȰɡ���\n"
    "�����Ϸ��ͣ�ı�������ȷ���ǲ����Կ�������������⣬���Ÿ���һ���Կ���������\n"
    "nVIDIA����http://www.nvidia.cn/Download/index.aspx?lang=cn\n"
    "AMD����http://support.amd.com/us/gpudownload/Pages/index.aspx\n"
    "\n"
    "�����ǰ��������Ϸ����ͻȻ�治���ˣ���ִ��һ����ϷĿ¼�е�update.bat��\n"
    "Ȼ���ٴ���Ϸ��\n"
    "\n"
    "��Ȼ���еĻ�����ȥhttp://www.thbattle.net������Թ����"
);


int execute(const char *app, const char* args)
{
    PROCESS_INFORMATION pinfo;
    STARTUPINFO sinfo;
    BOOL rst;
    DWORD exitcode = 1;
    
    ZeroMemory(&sinfo, sizeof(sinfo));
    sinfo.cb = sizeof(sinfo);
    
    rst = CreateProcess(app, args, NULL, NULL, FALSE, 0, NULL, NULL, &sinfo, &pinfo);
    if(!rst) {
        return 1;
    }
    WaitForSingleObject(pinfo.hProcess, INFINITE);
    GetExitCodeProcess(pinfo.hProcess, &exitcode);
    
    return exitcode;
}


int __stdcall WinMain(HINSTANCE hInstance,
                     HINSTANCE hPrevInstance,
                     LPTSTR    lpCmdLine,
                     int       nCmdShow)
{
    int rst;
    rst = execute("Python27\\pythonw.exe", "pythonw.exe");
    if(rst) {
        // failed, install vcredist
        execute("Python27\\vcredist_x86.exe", "vcredist_x86.exe");
    }
    rst = execute("Python27\\pythonw.exe", "pythonw.exe src\\start_client.py");
    if(rst) {
        ShellExecute(0, "open", "update.bat", NULL, NULL, 0);
        MessageBox(NULL, ERROR_PROMPT, "��Ϸ������", MB_ICONINFORMATION);
    }
    return 0;
}