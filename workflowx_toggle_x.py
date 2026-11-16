from comfy_api.latest import io


class ToggleXController(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        connection_type = io.MatchType.Template("toggle_x")
        source = io.MatchType.Input("input", connection_type, optional=True)
        choices = io.Autogrow.TemplatePrefix(source, prefix="input", min=0, max=100)
        return io.Schema(
            node_id="WorkflowXToggleXController",
            display_name="ToggleX Controller",
            category="WorkflowX",
            description="Connect alternative sources and select one in Quick ToggleX.",
            inputs=[io.Autogrow.Input("choices", choices)],
            outputs=[io.MatchType.Output(connection_type, display_name="selected")],
        )

    @classmethod
    def validate_inputs(cls, choices):
        if len(choices) != 1:
            return "Select one connected input for this ToggleX Controller in Quick ToggleX."
        return True

    @classmethod
    def execute(cls, choices):
        validation = cls.validate_inputs(choices)
        if validation is not True:
            raise ValueError(validation)
        return io.NodeOutput(next(iter(choices.values())))
