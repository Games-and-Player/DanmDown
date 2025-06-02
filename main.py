#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站完整弹幕下载器 - 修正版
模拟 jijidown_dm_fix.js 的逻辑：先获取实时弹幕，再从发布日期开始智能获取历史弹幕
"""

import html
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import requests


class DanmakuElement:
    """弹幕元素类"""
    def __init__(self, data: Dict):
        self.id = data.get('id', 0)
        self.progress = data.get('progress', 0)  # 毫秒
        self.mode = data.get('mode', 1)
        self.fontsize = data.get('fontsize', 25)
        self.color = data.get('color', 16777215)
        self.ctime = data.get('ctime', 0)
        self.pool = data.get('pool', 0)
        self.midHash = data.get('midHash', '')
        self.content = data.get('content', '')
        self.weight = data.get('weight', 0)

    def to_xml_element(self) -> str:
        """转换为XML弹幕格式"""
        p_attr = f"{self.progress / 1000:.3f},{self.mode},{self.fontsize},{self.color},{self.ctime},{self.pool},{self.midHash},{self.id}"
        content_escaped = html.escape(self.content)
        return f'<d p="{p_attr}">{content_escaped}</d>'

    def get_unique_id(self) -> str:
        """生成唯一标识，用于去重（模拟JS版本的逻辑）"""
        # 模拟 JS 版本的 generateDanmakuId 逻辑
        return f"{self.progress or 1}_{len(self.content)}_{hash(self.midHash) % (2**32)}"


class ProtobufDecoder:
    """简单的protobuf解码器"""
    
    @staticmethod
    def decode_varint(data: bytes, offset: int) -> tuple:
        """解码varint"""
        result = 0
        shift = 0
        pos = offset
        
        while pos < len(data):
            byte = data[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
            
        return result, pos

    @staticmethod
    def decode_string(data: bytes, offset: int, length: int) -> str:
        """解码字符串"""
        try:
            return data[offset:offset + length].decode('utf-8')
        except UnicodeDecodeError:
            return data[offset:offset + length].decode('utf-8', errors='ignore')

    @classmethod
    def decode_danmaku_response(cls, data: bytes) -> List[DanmakuElement]:
        """解码弹幕响应"""
        danmaku_list = []
        pos = 0
        
        while pos < len(data):
            try:
                field_tag, pos = cls.decode_varint(data, pos)
                field_number = field_tag >> 3
                wire_type = field_tag & 0x7
                
                if field_number == 1 and wire_type == 2:  # elems字段
                    length, pos = cls.decode_varint(data, pos)
                    danmaku_data = cls.decode_danmaku_element(data[pos:pos + length])
                    if danmaku_data:
                        danmaku_list.append(DanmakuElement(danmaku_data))
                    pos += length
                else:
                    if wire_type == 0:
                        _, pos = cls.decode_varint(data, pos)
                    elif wire_type == 2:
                        length, pos = cls.decode_varint(data, pos)
                        pos += length
                    else:
                        break
            except Exception as e:
                print(f"解码错误: {e}")
                break
                
        return danmaku_list

    @classmethod
    def decode_danmaku_element(cls, data: bytes) -> Optional[Dict]:
        """解码单个弹幕元素"""
        element = {}
        pos = 0
        
        while pos < len(data):
            try:
                field_tag, pos = cls.decode_varint(data, pos)
                field_number = field_tag >> 3
                wire_type = field_tag & 0x7
                
                if wire_type == 0:  # varint
                    value, pos = cls.decode_varint(data, pos)
                    field_map = {1: 'id', 2: 'progress', 3: 'mode', 4: 'fontsize', 
                               5: 'color', 8: 'ctime', 9: 'weight', 11: 'pool'}
                    if field_number in field_map:
                        element[field_map[field_number]] = value
                        
                elif wire_type == 2:  # length-delimited (string)
                    length, pos = cls.decode_varint(data, pos)
                    string_value = cls.decode_string(data, pos, length)
                    string_map = {6: 'midHash', 7: 'content', 12: 'idStr'}
                    if field_number in string_map:
                        element[string_map[field_number]] = string_value
                    pos += length
                else:
                    break
            except Exception:
                break
                
        return element if element else None


class BilibiliDanmakuDownloader:
    """B站完整弹幕下载器 - 模拟jijidown_dm_fix.js逻辑"""
    
    def __init__(self):
        # 待写 通过外部导入 cookies
        cookies = {}
        self.session = requests.Session()
        self.session.cookies.update(cookies)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Sec-Fetch-Site': 'same-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Accept': 'application/x-protobuf',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br'
        })
        self.id_pool: Set[str] = set()  # 用于去重，模拟JS版本

    def merge_danmaku_in_place(self, target_list: List[DanmakuElement], new_list: List[DanmakuElement]):
        """原地合并弹幕列表，模拟JS版本的mergeDanmakuInPlace函数"""
        if not hasattr(target_list, 'id_pool'):
            # 初始化id_pool
            for danmaku in target_list:
                unique_id = danmaku.get_unique_id()
                self.id_pool.add(unique_id)
        
        for danmaku in new_list:
            unique_id = danmaku.get_unique_id()
            if unique_id not in self.id_pool:
                target_list.append(danmaku)
                self.id_pool.add(unique_id)

    def get_current_danmaku_info(self, cid: int) -> tuple:
        """获取当前弹幕信息，由于XML API已废弃，改为通过实时弹幕接口估算"""
        print("📋 正在获取弹幕信息...")
        
        # 尝试获取第一段实时弹幕来估算总数
        try:
            url = f"https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index=1"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200 and len(response.content) > 0:
                first_segment = ProtobufDecoder.decode_danmaku_response(response.content)
                if first_segment:
                    # 粗略估算：每段约300-500条弹幕，估算总段数
                    estimated_total = len(first_segment) * 20  # 假设有20段左右
                    print(f"📊 估算弹幕总数: ~{estimated_total}, 当前获取样本: {len(first_segment)}条")
                    return estimated_total, []
            
            print("📊 无法获取弹幕信息，使用默认值")
            return 5000, []  # 使用默认值
            
        except Exception as e:
            print(f"获取弹幕信息失败: {e}")
            return 5000, []

    def get_segmented_danmaku(self, cid: int) -> List[DanmakuElement]:
        """获取分段弹幕（实时弹幕），模拟JS版本的getSegmentedDanmaku"""
        danmaku_list = []
        segment_index = 1
        
        print("⚡ 正在获取实时弹幕...")
        
        while segment_index <= 100:
            url = f"https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid={cid}&segment_index={segment_index}"
            
            try:
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 304:
                    print(f"分段 {segment_index}: 无新内容 (304)，停止获取")
                    break
                elif response.status_code != 200:
                    print(f"分段 {segment_index}: HTTP错误 {response.status_code}")
                    if response.status_code == 412:
                        print("可能需要重新登录或验证cookies")
                    break
                
                if len(response.content) == 0:
                    print(f"分段 {segment_index}: 响应为空，停止获取")
                    break
                
                segment_danmaku = ProtobufDecoder.decode_danmaku_response(response.content)
                
                if not segment_danmaku:
                    print(f"分段 {segment_index}: 解码后无弹幕数据，停止获取")
                    break
                
                old_count = len(danmaku_list)
                self.merge_danmaku_in_place(danmaku_list, segment_danmaku)
                new_count = len(danmaku_list) - old_count
                
                print(f"分段 {segment_index}: 获取 {len(segment_danmaku)} 条，新增 {new_count} 条，总计 {len(danmaku_list)} 条")
                
                # 如果连续几段都没有新增，可能已经获取完毕
                if new_count == 0:
                    print(f"分段 {segment_index}: 无新增弹幕，可能已获取完毕")
                    break
                
                segment_index += 1
                time.sleep(0.5)
                
            except Exception as e:
                print(f"获取分段 {segment_index} 弹幕失败: {e}")
                break
        
        print(f"实时弹幕获取完成: {len(danmaku_list)}条")
        return danmaku_list

    def get_history_danmaku_js_style(self, cid: int, video_date: Optional[datetime], 
                                   start_days: int = 0, end_days: int = 1, 
                                   target_count: int = 5000) -> List[DanmakuElement]:
        """模拟JS版本的历史弹幕获取逻辑"""
        if not video_date:
            print("未提供视频发布日期，跳过历史弹幕获取")
            return []
        
        print("📚 正在获取历史弹幕...")
        if start_days != 0 or end_days != 1:
            print(f"下载时段: 第{start_days}-{end_days}天")
        else:
            print("使用默认时段: 从发布日期开始")
        
        aldanmu = []  # 所有历史弹幕
        ldanmu = []   # 当前查询的弹幕
        first_date = 0
        ondanmu = target_count  # 目标弹幕数
        
        # 模拟JS逻辑：计算开始查询的日期
        base_date = video_date
        if end_days != -1:
            # 从发布日期 + end_days 开始查询，但实际上JS会从当前日期开始
            # 重新检查JS逻辑：实际上应该从昨天开始
            current_date = datetime.now() - timedelta(days=1)
        else:
            # 如果end_days=-1，从昨天开始查询
            current_date = datetime.now() - timedelta(days=1)
        
        # 计算最早查询到的日期（发布日期 + start_days）
        start_date = base_date + timedelta(days=start_days)
        
        print(f"从 {current_date.strftime('%Y-%m-%d')} 开始查询，最早到 {start_date.strftime('%Y-%m-%d')}")
        
        while current_date >= start_date:
            if first_date != 0:
                print("等待2秒...")
                time.sleep(2)
            
            # 模拟JS逻辑：如果first_date为0或者弹幕数量达到阈值，则查询新日期
            if first_date == 0 or len(ldanmu) >= min(ondanmu, 5000) * 0.5:
                date_str = current_date.strftime('%Y-%m-%d')
                url = f"https://api.bilibili.com/x/v2/dm/web/history/seg.so?type=1&date={date_str}&oid={cid}"
                
                print(f"{date_str}: 查询中...")
                
                try:
                    response = self.session.get(url, timeout=10)
                    
                    print(f"响应状态: {response.status_code}, 响应长度: {len(response.content)} 字节")
                    
                    if response.status_code == 200:
                        if len(response.content) == 0:
                            print(f"{date_str}: 响应为空")
                            ldanmu = []
                        else:
                            ldanmu = ProtobufDecoder.decode_danmaku_response(response.content)
                            
                            if ldanmu:
                                # 合并弹幕
                                self.merge_danmaku_in_place(aldanmu, ldanmu)
                                print(f"{date_str}: +{len(ldanmu)}条，总计{len(aldanmu)}条")
                                
                                # 关键：模拟JS逻辑，根据弹幕时间戳调整下次查询日期
                                min_ctime = min(d.ctime for d in ldanmu)
                                
                                if first_date != 0 and first_date - min_ctime < 86400:
                                    # 如果时间差小于1天，向前推1天
                                    tfirstdate = min_ctime - 86400
                                else:
                                    tfirstdate = min_ctime
                                
                                first_date = tfirstdate
                                current_date = datetime.fromtimestamp(first_date)
                                print(f"根据弹幕时间戳，下次查询日期调整为: {current_date.strftime('%Y-%m-%d')}")
                                
                            else:
                                print(f"{date_str}: 解码后无弹幕数据")
                                ldanmu = []
                    elif response.status_code == 412:
                        print(f"{date_str}: 需要验证 (412)，可能需要登录")
                        ldanmu = []
                    else:
                        print(f"{date_str}: 请求失败 ({response.status_code})")
                        if response.text:
                            print(f"错误响应: {response.text[:200]}")
                        ldanmu = []
                        
                except Exception as e:
                    print(f"{date_str}: 获取失败 - {e}")
                    ldanmu = []
            
            # 模拟JS逻辑：弹幕密度检查
            if len(ldanmu) < min(ondanmu, 5000) * 0.5:
                print("弹幕密度过低，停止历史查询")
                break
            
            # 如果first_date为0，按天递减（这种情况基本不会发生，因为有了智能跳转）
            if first_date == 0:
                current_date -= timedelta(days=1)
        
        print(f"历史弹幕获取完成: {len(aldanmu)}条")
        return aldanmu

    def get_complete_danmaku_js_style(self, cid: int, video_date: Optional[datetime] = None, 
                                    start_days: int = 0, end_days: int = None) -> List[DanmakuElement]:
        """完全模拟JS版本的弹幕获取逻辑"""
        
        # 如果没有指定end_days，默认从发布日期开始向前查询
        if end_days is None:
            if video_date:
                # 从发布日期开始，向前查询一段合理的时间
                end_days = 1  # 从发布日期后1天开始
            else:
                end_days = -1  # 没有发布日期时才从当前日期开始
        
        # 1. 获取弹幕信息（估算）
        maxlimit, current_danmaku = self.get_current_danmaku_info(cid)
        
        all_danmaku_lists = []
        if current_danmaku:
            all_danmaku_lists.append(current_danmaku)
        
        # 2. 先获取实时弹幕（与JS版本顺序一致）
        print("⚡ 首先获取实时弹幕...")
        segmented_danmaku = self.get_segmented_danmaku(cid)
        if segmented_danmaku:
            all_danmaku_lists.append(segmented_danmaku)
            print(f"实时弹幕获取完成: {len(segmented_danmaku)} 条")
        
        # 3. 获取历史弹幕作为补充
        if video_date and maxlimit > 0:
            history_danmaku = self.get_history_danmaku_js_style(cid, video_date, start_days, end_days, maxlimit)
            if history_danmaku:
                all_danmaku_lists.append(history_danmaku)
                print(f"历史弹幕作为补充: {len(history_danmaku)} 条")
        
        # 4. 合并所有弹幕
        print("🔄 正在合并弹幕数据...")
        merged_danmaku = []
        id_pool = set()
        
        for i, danmaku_list in enumerate(all_danmaku_lists):
            list_name = ["当前弹幕", "实时弹幕", "历史弹幕"][i] if i < 3 else f"列表{i+1}"
            old_count = len(merged_danmaku)
            
            for danmaku in danmaku_list:
                unique_id = danmaku.get_unique_id()
                if unique_id not in id_pool:
                    id_pool.add(unique_id)
                    merged_danmaku.append(danmaku)
            
            new_count = len(merged_danmaku) - old_count
            print(f"  {list_name}: 原始 {len(danmaku_list)} 条，新增 {new_count} 条")
        
        print(f"✅ 合并完成！共获取 {len(merged_danmaku)} 条弹幕")
        return merged_danmaku

    def save_danmaku_xml(self, danmaku_list: List[DanmakuElement], filename: str, cid: int):
        """保存弹幕为XML格式"""
        # 按播放时间排序
        danmaku_list.sort(key=lambda x: x.progress)
        
        xml_content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<i>',
            '<chatserver>chat.bilibili.com</chatserver>',
            '<chatid>0</chatid>',
            '<mission>0</mission>',
            f'<maxlimit>{len(danmaku_list)}</maxlimit>',
            '<state>0</state>',
            '<real_name>0</real_name>',
            '<source>JJDownPythonPort</source>',
            f'<info>{{"cid": {cid}, "total": {len(danmaku_list)}, "download_time": "{datetime.now().isoformat()}"}}</info>'
        ]
        
        for danmaku in danmaku_list:
            xml_content.append(danmaku.to_xml_element())
        
        xml_content.append('</i>')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_content))
        
        print(f"弹幕已保存到: {filename}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python bilibili_danmaku_downloader.py <cid> [选项]")
        print("选项:")
        print("  --publish-date YYYY-MM-DD  指定视频发布日期")
        print("  --start-days N            从发布日期开始的天数（默认0）")
        print("  --end-days N              到发布日期的天数（默认从发布日期+1天开始）")
        print("示例: python bilibili_danmaku_downloader.py 123456789")
        print("      python bilibili_danmaku_downloader.py 123456789 --publish-date 2023-01-01")
        print("      python bilibili_danmaku_downloader.py 123456789 --publish-date 2023-01-01 --start-days 0 --end-days 30")
        sys.exit(1)
    
    try:
        cid = int(sys.argv[1])
    except ValueError:
        print("错误: CID必须是数字")
        sys.exit(1)
    
    # 解析参数
    video_date = None
    start_days = 0
    end_days = None  # 默认为None，让逻辑自动处理
    
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == '--publish-date' and i + 1 < len(args):
            try:
                video_date = datetime.strptime(args[i + 1], '%Y-%m-%d')
                i += 2
            except ValueError:
                print("错误: --publish-date 参数格式应为 YYYY-MM-DD")
                sys.exit(1)
        elif args[i] == '--start-days' and i + 1 < len(args):
            try:
                start_days = int(args[i + 1])
                i += 2
            except ValueError:
                print("错误: --start-days 必须是整数")
                sys.exit(1)
        elif args[i] == '--end-days' and i + 1 < len(args):
            try:
                end_days = int(args[i + 1])
                i += 2
            except ValueError:
                print("错误: --end-days 必须是整数")
                sys.exit(1)
        else:
            print(f"未知参数: {args[i]}")
            sys.exit(1)
    
    downloader = BilibiliDanmakuDownloader()
    
    print(f"🎬 开始下载CID {cid} 的完整弹幕...")
    if video_date:
        print(f"📅 视频发布日期: {video_date.strftime('%Y-%m-%d')}")
        if start_days != 0 or end_days is not None:
            end_desc = str(end_days) if end_days is not None else "自动"
            print(f"⏰ 下载时段: 第{start_days}-{end_desc}天")
    
    # 获取完整弹幕（使用JS版本逻辑）
    danmaku_list = downloader.get_complete_danmaku_js_style(cid, video_date, start_days, end_days)
    
    if not danmaku_list:
        print("❌ 未获取到任何弹幕")
        sys.exit(1)
    
    # 保存为XML文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"danmaku_{cid}_{timestamp}.xml"
    downloader.save_danmaku_xml(danmaku_list, filename, cid)
    
    print("🎉 下载完成!")


if __name__ == "__main__":
    main()