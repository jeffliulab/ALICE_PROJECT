extends CharacterBody2D # 假设你的NPC根节点是CharacterBody2D

@export var dialogue_lines: Array[String] = [
	"你好，旅行者！", 
	"我叫阿伟，是这个村庄的守卫。",
	"最近村庄周围的史莱姆有点多...",
	"如果你能帮忙清理一些，我会非常感激的。",
	"一定要注意安全！"
]
var player_in_range = false
var dialogue_ui_scene: PackedScene # 用于加载对话框场景

func _ready():
	# 确保DialogueArea子节点存在
	# 注意：这里的路径是相对于NPC根节点的，如果你的DialogueArea直接是子节点，就是"$DialogueArea"
	# 如果你的Area2D名字不是DialogueArea，请修改
	var dialogue_area = $DialogueArea as Area2D # 假设你将Area2D命名为DialogueArea
	if dialogue_area:
		# 这些连接在编辑器中完成会更好，但在这里也可以确保
		# dialogue_area.body_entered.connect(_on_DialogueArea_body_entered)
		# dialogue_area.body_exited.connect(_on_DialogueArea_body_exited)
		pass # 如果在编辑器连接了，这里就不需要再connect了

	# 预加载对话UI场景
	dialogue_ui_scene = preload("res://dialogue_ui.tscn") # 替换为你的对话UI场景路径


func _input(event):
	# 如果场景中已经存在一个对话框UI，则不执行任何操作，直接返回。
	# 这可以防止任何情况下重复开启对话。
	# 注意：这里的 "DialogueUI_Control" 必须和你的对话框场景的根节点名字一致
	if get_tree().root.find_child("DialogueUI_Control", true, false):
		return
		
	# 当玩家在范围内按下交互键时触发对话
	# 确保 "interact" 动作已经在项目设置 -> Input Map 中定义
	if player_in_range and event.is_action_pressed("interact"):
		start_dialogue()


func _on_dialogue_area_area_2d_body_entered(body: Node2D) -> void: # 这个函数名是Godot自动生成的，可能和_on_DialogueArea_body_entered略有不同，取决于你的Area2D节点名
	# 检查进入区域的是否是玩家
	if body.name == "Player": # 确保你的Player节点的name属性是"Player"
		player_in_range = true
		print("Player entered NPC dialogue range.")
		# TODO: 在这里显示一个提示，例如“按F键对话”


func _on_dialogue_area_area_2d_body_exited(body: Node2D) -> void: # 同样，函数名可能不同
	# 检查离开区域的是否是玩家
	if body.name == "Player":
		player_in_range = false
		print("Player exited NPC dialogue range.")
		# TODO: 隐藏提示


func start_dialogue():
	if dialogue_ui_scene:
		var dialogue_ui = dialogue_ui_scene.instantiate() as Control
		get_tree().root.add_child(dialogue_ui) # 将对话UI添加到场景根节点，这样它就可以显示在所有东西上面
		dialogue_ui.start(dialogue_lines) # 调用对话UI脚本中的方法来开始对话

		# 连接对话UI的结束信号，以便在对话结束后恢复游戏状态
		if dialogue_ui.has_signal("dialogue_finished"): # 检查对话UI是否有这个信号
			dialogue_ui.dialogue_finished.connect(_on_dialogue_finished)

		# 暂停玩家输入或移动，通常通过暂停整个游戏树来实现，或者禁用玩家脚本
		get_tree().paused = true # 这是一个简单的方法，适用于单人游戏且不需要后台处理的场景
	else:
		print("Error: Dialogue UI scene not loaded! Check path.")

func _on_dialogue_finished():
	# 对话结束后，恢复游戏状态
	get_tree().paused = false
	# TODO: 隐藏或销毁对话UI实例，如果它没有自动销毁的话
	# 例如：如果对话UI是动态添加到根节点的，并且它没有自己销毁，你可以在这里销毁它
	# var dialogue_ui_node = get_tree().root.get_node("DialogueUI") # 假设你的对话UI场景根节点叫DialogueUI
	# if dialogue_ui_node:
	#    dialogue_ui_node.queue_free()
