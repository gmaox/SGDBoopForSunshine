import os
import sys
import json
import time
import shutil
import struct
import requests
from pathlib import Path
from typing import List, Dict, Optional
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from zlib import crc32
import winreg  # 添加winreg导入以访问Windows注册表
import traceback  # 添加这个导入以获取堆栈信息
import urllib3  # 添加这个导入以禁用SSL警告
#PyInstaller -F SGDBoopForSunshine.py -i fav.ico --uac-admin
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #禁用SSL警告
API_VERSION = "3"
API_USER_AGENT = "SGDBoop/v1.3.1"
API_AUTH_TOKEN = "62696720-6f69-6c79-2070-65656e75733f"

class NonSteamApp:
    def __init__(self, index: int, name: str, appid: str, appid_old: str, app_type: str = "nonsteam-app"):
        self.index = index
        self.name = name
        self.appid = appid
        self.appid_old = appid_old
        self.type = app_type

class SGDBoop:
    def __init__(self):
        self.non_steam_apps_count = 0
        self.source_mods_count = 0
        self.gold_source_mods_count = 0
        self.api_returned_lines = 0
        self.APP_INSTALL_PATH = self.get_app_install_path()  # 获取Sunshine安装路径

    def get_log_filepath(self) -> Path:
        """获取日志文件路径"""
        if sys.platform == "win32":
            path = Path(os.path.dirname(sys.executable)) / "sgdboop_error.log"
        else:
            state_home = os.getenv("XDG_STATE_HOME")
            if state_home:
                path = Path(state_home)
            else:
                path = Path.home() / ".local" / "state"
            path.mkdir(parents=True, exist_ok=True)
            path = path / "sgdboop_error.log"
        return path

    def log_error(self, error: str, error_code: int):
        """记录错误信息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_path = self.get_log_filepath()
        
        # 获取堆栈信息
        stack_trace = traceback.format_exc()
        if stack_trace == "NoneType: None\n":  # 如果没有异常堆栈
            # 获取当前代码位置
            frame = traceback.extract_stack()[-2]  # -2 是因为当前函数调用占用了一帧
            filename, lineno, funcname, line = frame
            location_info = f"File: {filename}, Line: {lineno}, Function: {funcname}"
        else:
            location_info = stack_trace

        with open(log_path, "a", encoding='utf-8') as f:
            f.write(f"{timestamp} {error} [{error_code}]\n")
            f.write(f"Location:\n{location_info}\n")
            f.write("-" * 50 + "\n\n")
        print(f"Created logfile in {log_path}")

    def exit_with_error(self, error: str, error_code: int):
        """记录错误并退出"""
        self.log_error(error, error_code)
        # 在退出前显示错误消息框
        self.show_message_box("错误", f"{error}\n错误代码: {error_code}")
        sys.exit(error_code)

    def call_api(self, grid_types: str, grid_ids: str, mode: str) -> List[List[str]]:
        """调用SGDB API"""
        url = f"https://www.steamgriddb.com/api/sgdboop/{grid_types}/{grid_ids}"
        if mode == "nonsteam":
            url += "?nonsteam=1"

        headers = {
            "Authorization": f"Bearer {API_AUTH_TOKEN}",
            "X-BOOP-API-VER": API_VERSION,
            "User-Agent": API_USER_AGENT
        }

        response = requests.get(url, headers=headers)
        
        if response.status_code >= 400:
            error_msg = f"API Error: {response.text}"
            if response.text.startswith("error-"):
                error_msg = error_msg.replace("error-", " ")
                self.show_message_box("SGDBoop Error", error_msg)
            self.exit_with_error(error_msg, response.status_code)

        results = []
        for line in response.text.splitlines():
            if line:
                values = line.split(",")
                results.append(values)
                self.api_returned_lines += 1

        return results

    def get_app_install_path(self):
        """获取Sunshine安装路径"""
        app_name = "sunshine"
        try:
            # 打开注册表键，定位到安装路径信息
            registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                          r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
            # 遍历注册表中的子项，查找对应应用名称
            for i in range(winreg.QueryInfoKey(registry_key)[0]):
                subkey_name = winreg.EnumKey(registry_key, i)
                subkey = winreg.OpenKey(registry_key, subkey_name)
                try:
                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                    if app_name.lower() in display_name.lower():
                        install_location, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                        if os.path.exists(install_location):
                            return os.path.dirname(install_location)
                except FileNotFoundError:
                    continue
        except Exception as e:
            print(f"Error: {e}")
        print("未检测到安装目录！")
        return None

    def get_steam_base_dir(self) -> Optional[Path]:
        """获取Steam基础目录"""
        if sys.platform == "win32":
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
                path = winreg.QueryValueEx(key, "SteamPath")[0]
                return Path(path)
            except WindowsError:
                return None
        else:
            home = Path.home()
            flatpak_path = Path("/var/lib/flatpak/app/com.valvesoftware.Steam")
            
            if flatpak_path.exists():
                return home / ".var/app/com.valvesoftware.Steam/data/Steam"
            else:
                return home / ".steam/steam"

    def show_message_box(self, title: str, message: str):
        """显示消息框"""
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showinfo(title, message)  # 使用messagebox显示信息
        root.destroy()  # 销毁窗口

    def restart_service(self):
        """发送POST请求以重启服务"""
        try:
            response = requests.post('https://localhost:47990/api/restart', verify=False)
            if response.status_code == 200:
                print("sunshine服务重启")
            else:
                print(f"sunshine服务重启失败，状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"重启sunshine服务时发生错误: {str(e)}")

    def select_non_steam_app(self, sgdb_name: str, apps: List[NonSteamApp]) -> Optional[NonSteamApp]:
        """选择非Steam应用"""
        steam_cover_window = tk.Tk()
        steam_cover_window.title(f"SGDBoop for Sunshine: Pick a game for '{sgdb_name}'")
        
        # 设置窗口大小
        steam_cover_window.geometry("600x400")  # 设置窗口宽度为600，高度为400

        # 创建 Listbox 组件
        listbox = tk.Listbox(steam_cover_window, height=10, width=50)  # 设置Listbox的高度和宽度
        listbox.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

        # 将应用名称添加到 Listbox
        for app in apps:
            listbox.insert(tk.END, app.name)

        selected_app = None

        def on_select(event=None):  # 添加默认参数，使其可以同时处理事件和按钮点击
            nonlocal selected_app
            selection = listbox.curselection()
            if selection:
                selected_index = selection[0]
                selected_app = apps[selected_index]
                steam_cover_window.quit()
            else:
                # 如果没有选择任何项目，显示提示
                self.show_message_box("提示", "请先选择一个应用")

        def on_double_click(event):
            # 双击时直接确认选择
            on_select()

        # 绑定事件
        listbox.bind('<Double-Button-1>', on_double_click)  # 双击
        listbox.bind('<<ListboxSelect>>', lambda e: None)  # 禁用默认的选择事件

        # 创建按钮，使用相同的回调函数
        tk.Button(
            steam_cover_window, 
            text="——确认选择——", 
            command=on_select,
            width=20,  # 设置按钮宽度
            height=2   # 设置按钮高度
        ).pack(pady=10)
        
        steam_cover_window.mainloop()
        steam_cover_window.destroy()
        
        return selected_app

    def download_asset_file(self, app_id: str, url: str, asset_type: str, 
                          orientation: str, destination_dir: Path, 
                          non_steam_app: Optional[NonSteamApp] = None) -> Optional[Path]:
        """下载资源文件"""
        destination_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建输出文件名
        filename = destination_dir / f"{app_id}"
        if asset_type == "hero":
            filename = filename.with_suffix(".jpg").with_stem(f"{filename.stem}_hero")
        elif asset_type == "logo":
            filename = filename.with_suffix(".jpg").with_stem(f"{filename.stem}_logo")
        elif asset_type == "grid":
            if orientation == "p":
                filename = filename.with_suffix(".jpg").with_stem(f"{filename.stem}_SGDB")
            else:
                filename = filename.with_suffix(".jpg")
        elif asset_type == "icon":
            if non_steam_app is None:
                filename = filename.with_suffix(".jpg").with_stem(f"{filename.stem}_icon")
            else:
                extension = Path(url).suffix
                filename = filename.with_suffix(extension).with_stem(f"{filename.stem}_icon")

        # 下载文件
        response = requests.get(url, headers={"User-Agent": API_USER_AGENT})
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
        return None

    def get_non_steam_apps(self, include_mods: bool = True) -> List[NonSteamApp]:
        """从apps.json获取非Steam应用列表"""
        try:
            # 读取apps.json文件
            json_path = Path(self.APP_INSTALL_PATH) / "config/apps.json"  # 使用APP_INSTALL_PATH
            
            if not json_path.exists():
                self.exit_with_error("Could not find apps.json", 91)
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            apps = []
            for index, app in enumerate(data.get('apps', [])):
                name = app.get('name', '')
                if not name:
                    continue
                
                # 生成appid (使用name的crc32作为基础)
                appid = str(abs(crc32(name.encode())) % (2**32))
                
                # 生成old_appid (保持与原程序相似的格式)
                appid_old = str((int(appid) | 0x80000000) << 32 | 0x02000000)
                
                # 创建NonSteamApp对象
                non_steam_app = NonSteamApp(
                    index=index,
                    name=name,
                    appid=appid,
                    appid_old=appid_old
                )
                apps.append(non_steam_app)
                self.non_steam_apps_count += 1
            
            if not apps:
                self.show_message_box("SGDBoop Error", "Could not find any non-Steam apps.")
                self.exit_with_error("Could not find any non-Steam apps in apps.json.", 91)
            
            return apps
        
        except Exception as e:
            self.exit_with_error(f"Error reading apps.json: {str(e)}", 91)
            return []

    def main(self, args: List[str]):
        """主函数"""
        try:
            if len(args) <= 1 or not args[1].startswith("sgdb://"):
                # 弹出询问窗口
                response = messagebox.askquestion(
                    "选择操作",
                    "URI参数能确保steamgriddb能打开程序。您想要创建URI协议还是删除URI协议？\n是：创建URI协议，否：删除URI协议？",
                    icon='warning'
                )
                if response == 'yes':
                    self.create_uri_protocol()
                else:
                    self.delete_uri_protocol()
                return

            if args[1] == "unregister":
                self.delete_uri_protocol()
                return

            if not args[1].startswith("sgdb://boop"):
                self.exit_with_error("Invalid URI schema.", 81)

            if args[1] == "sgdb://boop/test":
                self.show_message_box("SGDBoop Test", "^_^/   SGDBoop is working!   \\^_^")
                return

            # 解析URI参数
            uri = args[1].replace("sgdb://boop/", "")
            parts = uri.split("/")
            
            if len(parts) < 2:
                self.exit_with_error("Invalid URI parameters.", 81)
            
            grid_types = parts[0]
            grid_ids = parts[1]
            mode = parts[2] if len(parts) > 2 else "default"

            # 调用API获取资源
            api_results = self.call_api(grid_types, grid_ids, mode)
            print(api_results)
            
            # 处理API返回的每个资源
            non_steam_app_data = None
            for result in api_results:
                if len(result) < 4:
                    self.exit_with_error("Invalid API response format.", 84)

                app_id, orientation, asset_url, asset_type = result[:4]
                asset_hash = result[4] if len(result) > 4 else None

                if app_id.startswith("nonsteam-"):
                    if non_steam_app_data is None:
                        apps = self.get_non_steam_apps(include_mods=not (
                            grid_types == "icon" or 
                            (grid_types == "steam" and asset_type == "icon")
                        ))
                        non_steam_app_data = self.select_non_steam_app(
                            app_id.split("-", 1)[1], 
                            apps
                        )
                        if not non_steam_app_data:
                            continue
                
                    app_id = non_steam_app_data.appid
                else:
                    input("请使用nonsteam来添加")
                    sys.exit(1)

                # 获取Steam目标目录，修改为指定路径
                steam_dest_dir = Path(self.APP_INSTALL_PATH) / "config/covers"

                # 下载资源文件
                outfile = self.download_asset_file(
                    app_id, asset_url, asset_type, orientation, 
                    steam_dest_dir, non_steam_app_data
                )
                
                if not outfile:
                    self.exit_with_error("Could not download asset file.", 84)

                # 更新apps.json中的image-path
                self.update_image_path_in_json(non_steam_app_data.name, outfile)
                
                # 弹出已完成提示框
                # 询问是否重启sunshine
                restart_response = messagebox.askquestion(
                    "下载完成,询问重启服务",
                    f"{non_steam_app_data.name} 的封面已成功下载到 {outfile}。\n是否重启Sunshine服务？"
                )
                if restart_response == 'yes':
                    self.restart_service()
                sys.exit(1)

                # 处理非Steam应用的特殊情况
                # if non_steam_app_data:
                #     if asset_type == "grid" and orientation == "l":
                #         self.create_old_id_symlink(non_steam_app_data, steam_dest_dir)
                #     elif asset_type == "icon":
                #         self.update_vdf(non_steam_app_data, outfile)

        except Exception as e:
            self.log_error(f"An error occurred: {str(e)}", 1)  # 记录错误信息
            self.exit_with_error(f"An error occurred: {str(e)}", 1)

    def create_uri_protocol(self):
        """创建SGDB URI协议处理程序"""
        log_filepath = self.get_log_filepath()
        popup_message = ""
        
        if sys.platform == "win32":
            import winreg
            try:
                # 获取当前程序路径
                exe_path = sys.executable
                
                # 注册协议处理程序
                commands = [
                    # 添加基本协议信息
                    ["HKEY_CLASSES_ROOT\\sgdb", "", "URL:sgdb Protocol"],
                    # 添加URL协议标记
                    ["HKEY_CLASSES_ROOT\\sgdb", "URL Protocol", ""],
                    # 添加命令 - 修改命令行参数格式
                    ["HKEY_CLASSES_ROOT\\sgdb\\Shell\\Open\\Command", "", f'"{exe_path}" "%1"'],
                    # 添加图标
                    ["HKEY_CLASSES_ROOT\\sgdb\\DefaultIcon", "", f'"{exe_path},0"']
                ]
                
                # 执行注册表操作
                for key_path, value_name, value_data in commands:
                    try:
                        # 分割注册表路径
                        parts = key_path.split("\\")
                        # 创建完整的路径
                        full_path = "\\".join(parts[1:])
                        # 创建或打开键
                        key = winreg.CreateKeyEx(getattr(winreg, parts[0]), full_path, 0, 
                                               winreg.KEY_WRITE | winreg.KEY_SET_VALUE)
                        # 设置值
                        if value_name:
                            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value_data)
                        else:
                            winreg.SetValue(key, "", winreg.REG_SZ, value_data)
                        winreg.CloseKey(key)
                    except WindowsError as e:
                        # 检查是否已经注册
                        try:
                            key = winreg.OpenKey(getattr(winreg, parts[0]), 
                                               "\\".join(parts[1:]) + "\\Shell\\Open\\Command")
                            winreg.CloseKey(key)
                            popup_message = (
                                "SGDBoop已经注册！\n"
                                "请前往 https://www.steamgriddb.com/boop 继续设置。\n\n"
                                "如果您移动了程序并想重新注册，请以管理员身份运行SGDBoop。\n"
                            )
                            self.show_message_box("SGDBoop Error", popup_message)
                            return
                        except WindowsError:
                            popup_message = "请以管理员身份运行此程序以进行注册！\n"
                            self.show_message_box("SGDBoop Error", popup_message)
                            return
                
                popup_message = (
                    "程序注册成功！\n\n"
                    "SGDBoop需要从浏览器运行！\n"
                    "请前往 https://www.steamgriddb.com/boop 继续设置。\n\n"
                    f"日志文件路径: {log_filepath}"
                )
                self.show_message_box("SGDBoop Information", popup_message)
                
            except Exception as e:
                self.exit_with_error(f"注册URI协议失败: {str(e)}", 80)
            
        else:
            # Linux系统不需要注册
            popup_message = (
                "SGDBoop is meant to be ran from a browser!\n"
                "Head over to https://www.steamgriddb.com/boop to continue setup.\n\n"
                f"Log file path: {log_filepath}"
            )
            self.show_message_box("SGDBoop Information", popup_message)

    def delete_uri_protocol(self):
        """删除SGDB URI协议处理程序"""
        if sys.platform == "win32":
            import winreg
            try:
                # 要删除的注册表项列表（从内到外的顺序）
                keys_to_delete = [
                    ["HKEY_CLASSES_ROOT", "sgdb\\Shell\\Open\\Command"],
                    ["HKEY_CLASSES_ROOT", "sgdb\\Shell\\Open"],
                    ["HKEY_CLASSES_ROOT", "sgdb\\Shell"],
                    ["HKEY_CLASSES_ROOT", "sgdb\\DefaultIcon"],
                    ["HKEY_CLASSES_ROOT", "sgdb"]
                ]
                
                # 逐个删除注册表项
                for root_key, sub_key in keys_to_delete:
                    try:
                        # 尝试以完整权限打开键
                        key = winreg.OpenKey(
                            getattr(winreg, root_key),
                            sub_key,
                            0,
                            winreg.KEY_ALL_ACCESS
                        )
                        winreg.CloseKey(key)  # 关闭键
                        # 删除键
                        winreg.DeleteKey(getattr(winreg, root_key), sub_key)
                    except WindowsError as e:
                        # 如果键不存在，继续下一个
                        if e.winerror == 2:  # 找不到文件
                            continue
                        # 如果是权限问题
                        elif e.winerror == 5:  # 访问被拒绝
                            try:
                                # 尝试直接删除
                                os.system(f'reg delete "HKEY_CLASSES_ROOT\\{sub_key}" /f')
                                continue
                            except:
                                self.show_message_box("错误", 
                                    "无法删除注册表项，请尝试以下步骤：\n"
                                    "1. 打开注册表编辑器(regedit)\n"
                                    "2. 导航到 HKEY_CLASSES_ROOT\\sgdb\n"
                                    "3. 右键删除该项\n"
                                    "或者重启电脑后重试"
                                )
                                return
                        else:
                            # 其他错误则记录并继续
                            print(f"删除 {sub_key} 时出错: {e}")
                            continue

                # 检查是否完全删除
                try:
                    # 尝试打开主键检查是否还存在
                    winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "sgdb")
                    self.show_message_box("警告", "部分注册表项可能未完全删除，请手动检查注册表。")
                except WindowsError as e:
                    if e.winerror == 2:  # 找不到文件，说明删除成功
                        self.show_message_box("成功", "程序注册已成功删除！")
                    else:
                        raise

            except Exception as e:
                error_msg = f"删除URI协议失败: {str(e)}"
                self.log_error(error_msg, 85)
                self.show_message_box("错误", error_msg)
        else:
            # Linux系统显示提示信息
            print("需要SGDB URL参数。\n示例: SGDBoop sgdb://boop/[ASSET_TYPE]/[ASSET_ID]")
            sys.exit(1)

    def update_image_path_in_json(self, app_name: str, new_image_path: Path):
        """更新apps.json中指定应用的image-path"""
        json_path = Path(self.APP_INSTALL_PATH) / "config/apps.json"  # 使用APP_INSTALL_PATH
        if not json_path.exists():
            json_path = Path("apps.json")  # 如果默认路径不存在，尝试当前目录
        
        if not json_path.exists():
            self.exit_with_error("Could not find apps.json", 91)

        try:
            with open(json_path, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                for app in data.get('apps', []):
                    if app.get('name') == app_name:
                        app['image-path'] = str(new_image_path)  # 更新image-path
                        break

                # 将更新后的数据写回文件
                f.seek(0)
                f.truncate()  # 清空文件
                json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"Updated image-path for {app_name} to {new_image_path}")

        except Exception as e:
            self.exit_with_error(f"Error updating apps.json: {str(e)}", 91)

def main():
    sgdboop = SGDBoop()
    sgdboop.main(sys.argv)

if __name__ == "__main__":
    main()
