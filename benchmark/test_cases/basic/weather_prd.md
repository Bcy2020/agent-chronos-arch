# Weather Station - Product Requirements Document

## Overview
A simple weather station system that records temperature readings from different locations. Users can add, view, update, and delete temperature records. Data is stored in memory during the session.

## External Interface
通过 `manage_weather(command, weather_data)` 函数调用实现天气记录管理操作。

```
输入: {"command": "add", "weather_data": {"location": "北京", "temperature": 25.5, "unit": "celsius"}}
输出: {"success": true, "message": "天气记录添加成功", "data": {"record_id": 1}}
```

## Core Features

### 1. Add Record
- 用户可添加温度记录（地点、温度值、单位）
- 每条记录获得唯一ID
- 单位支持：celsius, fahrenheit
- 自动记录时间戳
- 温度范围验证（不能低于绝对零度）

### 2. List Records
- 用户可列出所有温度记录
- 可按地点筛选
- 可按温度范围筛选（min_temp, max_temp）
- 输出显示：ID、地点、温度、单位、时间戳

### 3. Update Record
- 用户可修改温度记录（通过ID）
- 可修改温度值、单位
- 单位转换时自动计算新温度值
- 检查记录是否存在

### 4. Delete Record
- 用户可删除温度记录（通过ID）
- 检查记录是否存在

### 5. Convert Unit
- 用户可转换某条记录的温度单位
- Celsius → Fahrenheit: F = C × 9/5 + 32
- Fahrenheit → Celsius: C = (F - 32) × 5/9
- 记录的温度值和单位都会更新

### 6. Get Statistics
- 用户可获取温度统计信息
- 统计：最高温、最低温、平均温
- 可按地点筛选统计范围

## Technical Constraints
- 内存存储（无持久化）
- 温度为浮点数，精确到小数点后一位
- 时间戳格式：ISO 8601
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "add|list|update|delete|convert|stats",
  "weather_data": {
    "location": "地点名称（add时必填）",
    "temperature": 温度值（add/update时必填）,
    "unit": "celsius|fahrenheit（add/convert时必填）",
    "record_id": 记录ID（update/delete/convert时必填）,
    "location_filter": 地点筛选（list/stats时可选）,
    "min_temp": 最低温筛选（list时可选）,
    "max_temp": 最高温筛选（list时可选）
  }
}
```

### Output
```json
{
  "success": true/false,
  "message": "操作结果消息",
  "data": {"返回数据"}
}
```

## Example Usage
```
manage_weather("add", {"location": "北京", "temperature": 25.5, "unit": "celsius"})
→ {"success": true, "message": "记录添加成功，ID=1", "data": {"record_id": 1, "timestamp": "2024-01-20T10:00:00"}}

manage_weather("add", {"location": "上海", "temperature": 78, "unit": "fahrenheit"})
→ {"success": true, "message": "记录添加成功，ID=2", "data": {"record_id": 2, "timestamp": "..."}}

manage_weather("list", {"location_filter": "北京"})
→ {"success": true, "message": "共1条记录", "data": {"records": [{"id":1, "location":"北京", "temperature":25.5, "unit":"celsius", ...}]}}

manage_weather("update", {"record_id": 1, "temperature": 30.0})
→ {"success": true, "message": "记录更新成功", "data": {"record_id": 1}}

manage_weather("convert", {"record_id": 2, "unit": "celsius"})
→ {"success": true, "message": "单位转换成功", "data": {"record_id": 2, "temperature": 25.56, "unit": "celsius"}}

manage_weather("delete", {"record_id": 1})
→ {"success": true, "message": "记录删除成功", "data": {"record_id": 1}}

manage_weather("stats", {"location_filter": "上海"})
→ {"success": true, "message": "统计完成", "data": {"max": 25.56, "min": 25.56, "avg": 25.56, "count": 1}}
```

## Success Criteria
- 所有6种操作正确执行
- 单位转换公式正确
- 温度范围验证正确（不低于绝对零度）
- 筛选功能正确
- 统计计算正确
- 错误处理完善（无效ID、无效单位、无效温度）