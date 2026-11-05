IMGUI_DIR ?= third_party/imgui
CXX ?= c++
CXXFLAGS ?= -O3 -DNDEBUG -std=c++17
TARGET := guimark-imgui
IMGUI_SOURCES := $(IMGUI_DIR)/imgui.cpp $(IMGUI_DIR)/imgui_draw.cpp \
	$(IMGUI_DIR)/imgui_tables.cpp $(IMGUI_DIR)/imgui_widgets.cpp

.PHONY: all deps clean
all: $(TARGET)

$(TARGET): main.cpp $(IMGUI_SOURCES)
	$(CXX) $(CXXFLAGS) -I$(IMGUI_DIR) main.cpp $(IMGUI_SOURCES) -o $@

deps:
	mkdir -p $(dir $(IMGUI_DIR))
	git clone --depth 1 --branch v1.92.9b https://github.com/ocornut/imgui.git $(IMGUI_DIR)
	test "$$(git -C $(IMGUI_DIR) rev-parse HEAD)" = f1cc2ae15e53a861a874c3034aae6798fde194ab

clean:
	rm -f $(TARGET)
