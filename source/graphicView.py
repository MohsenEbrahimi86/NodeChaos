from source.graphicScene import ChaosGraphicScene
from source.node import *
from source.data import *
from source.curve import Curve
import math
from source import detailEditor

_ZOOM_STEP = 1.1


class ChaosGraphicView(QGraphicsView):
    def __init__(self, parent):
        super(ChaosGraphicView, self).__init__(parent)
        self.node_chaos_editor = parent
        self.scene = ChaosGraphicScene()
        self.scene.setSceneRect(0, 0, 99999, 99999)
        self.setScene(self.scene)

        self.path = QGraphicsPathItem()
        self.path.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.path.setPen(QPen(Qt.white, 5))
        self.scene.addItem(self.path)
        self.selected_knob = None
        for node in Data.nodes:
            self.add_node(node)

        self.__panning = False
        self.__last_pos = QPointF()
        self.__current_zoom = 1
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.node_editor = detailEditor.DetailEditor(None, self)
        self.node_editor.hide()

    def add_node(self, node):
        Data.add_node(node)
        self.scene.addItem(node)
        for knob in node.knobs:
            self.scene.addItem(knob)
            knob.setParentItem(node)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            if type(item) == Node:
                self.node_editor.open(item)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_N:
            self.add_node(Node(V2d(
                self.mapToScene(self.__last_pos).x(),
                self.mapToScene(self.__last_pos).y()))
            )
        elif event.key() == Qt.Key_F:
            self.frame_selected()
        elif event.key() == Qt.Key_Delete:
            self.delete_selected()
        super(ChaosGraphicView, self).keyPressEvent(event)

    def delete_selected(self):
        # todo: load data delete all add new node, save data again, previous nodes still there
        items = self.scene.selectedItems()
        if not items: return
        for item in items:
            if type(item) == Node:
                Data.remove_node(item)
                item.delete()
            elif type(item) == Curve:
                item.delete()

    def frame_selected(self, nodes=[], zoom=True):
        if len(Data.nodes) == 0: return
        if not nodes:
            nodes = Data.nodes
        item_rect = nodes[0].rect()
        for item in nodes:
            if type(item) == Node:
                if item.rect().top() < item_rect.top():
                    item_rect.setTop(item.rect().top())
                if item.rect().left() < item_rect.left():
                    item_rect.setLeft(item.rect().left())
                if item.rect().bottom() > item_rect.bottom():
                    item_rect.setBottom(item.rect().bottom())
                if item.rect().right() > item_rect.right():
                    item_rect.setRight(item.rect().right())
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.centerOn(item_rect.center())
        if zoom:
            self.scale(1 / self.__current_zoom, 1 / self.__current_zoom)
            self.__current_zoom = self.transform().m11()

    def wheelEvent(self, event:QWheelEvent):
        if event.delta() < 0 and self.__current_zoom < 0.05:
            return
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        zoom = _ZOOM_STEP if event.delta() >= 0 else 1.0/_ZOOM_STEP
        rect = self.scene.sceneRect()
        rect.setLeft(rect.left() + (rect.width() * 0.1 * math.copysign(1, event.delta())))
        rect.setRight(rect.right() + (rect.width() * -0.1 * math.copysign(1, event.delta())))
        rect.setTop(rect.top() + (rect.height() * 0.1 * math.copysign(1, event.delta())))
        rect.setBottom(rect.bottom() + (rect.height() * -0.1 * math.copysign(1, event.delta())))
        self.scale(zoom, zoom)
        self.__current_zoom = self.transform().m11()
        wheel = math.copysign(1, event.delta())

    def mousePressEvent(self, event:QMouseEvent):
        self.__panning = False
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.__panning = True
            self.__last_pos = event.pos()
            self.setCursor(Qt.SizeAllCursor)

        item = self.itemAt(event.pos())
        if item:
            if type(item) == Knob:
                if self.selected_knob:
                    if item == self.selected_knob:
                        self.toggle_connection(False)
                    else:
                        self.add_connection(item)
                else:
                    self.selected_knob = item
                    self.toggle_connection(True)
                    self.draw_current_edge(event.pos())
            elif type(item) == Curve:
                item.highlighted = True
            else:
                self.toggle_connection(False)
        else:
            self.toggle_connection(False)
        super(ChaosGraphicView, self).mousePressEvent(event)

    def add_connection(self, item):
        if self.selected_knob.knob_type == item.knob_type:
            self.toggle_connection(False)
            return
        if self.selected_knob.knob_type == KnobType.Output and item.knob_type == KnobType.Input:
            self.selected_knob.node.add_connection(self.scene, self.selected_knob, item)
        else:
            item.node.add_connection(self.scene, item, self.selected_knob)
        self.toggle_connection(False)

    def toggle_connection(self, toggle):
        if not toggle:
            self.selected_knob = None
        self.path.setVisible(toggle)

    def mouseReleaseEvent(self, event:QMouseEvent):
        self.__panning = False
        self.setCursor(Qt.ArrowCursor)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        super(ChaosGraphicView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event:QMouseEvent):
        self.draw_current_edge(event.pos())
        if self.pan(event.pos()):
            self.__last_pos = event.pos()
            return
        self.__last_pos = event.pos()
        super(ChaosGraphicView, self).mouseMoveEvent(event)

    def pan(self, pos):
        if self.__panning:
            delta = (
                (self.mapToScene(pos) * self.__current_zoom)
                - (self.mapToScene(self.__last_pos) * self.__current_zoom))*-1.0
            length = (delta.x() + delta.y()) / 2
            if length != 0:
                center = QPoint(self.viewport().width() / 2 + delta.x(),
                                self.viewport().height() / 2 + delta.y())
                self.centerOn(self.mapToScene(center))
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
                rect = self.scene.sceneRect()
                if delta.x() < 0:
                    if self.horizontalScrollBar().value() <= self.horizontalScrollBar().minimum():
                        self.horizontalScrollBar().setMinimum(self.horizontalScrollBar().minimum() + delta.x())
                        rect.setLeft(rect.left() + delta.x())
                elif delta.x() > 0:
                    if self.horizontalScrollBar().value() >= self.horizontalScrollBar().maximum():
                        self.horizontalScrollBar().setMaximum(self.horizontalScrollBar().maximum() + delta.x())
                        rect.setRight(rect.right() + delta.x())
                if delta.y() < 0:
                    if self.verticalScrollBar().value() <= self.verticalScrollBar().minimum():
                        self.verticalScrollBar().setMinimum(self.verticalScrollBar().minimum() + delta.y())
                        rect.setTop(rect.top() + delta.y())
                elif delta.y() > 0:
                    if self.verticalScrollBar().value() >= self.verticalScrollBar().maximum():
                        self.verticalScrollBar().setMaximum(self.verticalScrollBar().maximum() + delta.y())
                        rect.setBottom(rect.bottom() + delta.y())
                return True
        return False

    def draw_current_edge(self, pos):
        pos = self.mapToScene(pos)
        if self.selected_knob:
            maped = self.selected_knob.mapToScene(self.selected_knob.rect().center())
            t1 = QPointF(-50, 0)
            t2 = QPointF(50, 0)
            if self.selected_knob.knob_type == KnobType.Output:
                t1 = QPointF(50, 0)
                t2 = QPointF(-50, 0)
            path = QPainterPath()
            path.moveTo(maped)
            path.cubicTo(
                maped.x() + t1.x(),
                maped.y() + t1.y(),
                pos.x() + t2.x(),
                pos.y() + t2.y(),
                pos.x(),
                pos.y())
            self.path.setPath(path)
            self.update()