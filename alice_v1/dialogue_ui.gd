# dialogue_ui.gd (极简版本)
extends Control

# 对话结束时发出的信号，让NPC知道可以恢复游戏了
signal dialogue_finished

# 节点引用：只需要获取用于显示文本的Label节点
@onready var dialogue_label: Label = $Panel/VBoxContainer/DialogueText

# 内部变量
var dialogue_lines: Array[String] = []
var current_line_index: int = 0


func _ready() -> void:
	# 默认隐藏，等待NPC调用
	visible = false
	# 确保游戏暂停时，UI依然可以接收输入
	process_mode = PROCESS_MODE_ALWAYS


# 由NPC调用的入口函数
func start(lines: Array[String]) -> void:
	# 如果没有提供对话内容，直接结束，避免出错
	if lines.is_empty():
		_finish_and_cleanup()
		return

	# 保存对话内容，并显示第一句话
	self.dialogue_lines = lines
	self.current_line_index = 0
	dialogue_label.text = dialogue_lines[current_line_index]
	
	# 显示对话框
	visible = true


# 处理玩家输入
func _input(event: InputEvent) -> void:
	# 如果对话框不可见，不执行任何操作
	if not visible:
		return

	# 如果玩家按下了 "interact" 键
	if event.is_action_pressed("interact"):
		_advance_dialogue()
		get_viewport().set_input_as_handled()



# 推进对话逻辑
func _advance_dialogue() -> void:
	# 将行数索引+1
	current_line_index += 1

	# 检查是否还有下一句话
	if current_line_index < dialogue_lines.size():
		# 如果有，就显示下一句话
		dialogue_label.text = dialogue_lines[current_line_index]
	else:
		# 如果没有了，就结束对话并清理
		_finish_and_cleanup()


# 结束对话，并从场景中移除自己
func _finish_and_cleanup() -> void:
	emit_signal("dialogue_finished")
	queue_free()
