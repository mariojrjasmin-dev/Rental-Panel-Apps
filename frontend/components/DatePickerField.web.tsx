import { useState, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal, FlatList } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type Props = {
  date: Date;
  onDateChange: (date: Date) => void;
  minimumDate?: Date;
  label: string;
  accentColor?: string;
};

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const DAYS_HEADER = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

export default function DatePickerField({ date, onDateChange, minimumDate, label, accentColor = '#FF3B30' }: Props) {
  const [show, setShow] = useState(false);
  const [viewYear, setViewYear] = useState(date.getFullYear());
  const [viewMonth, setViewMonth] = useState(date.getMonth());

  const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const prevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(viewYear - 1); }
    else { setViewMonth(viewMonth - 1); }
  };

  const nextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(viewYear + 1); }
    else { setViewMonth(viewMonth + 1); }
  };

  const selectDate = (day: number) => {
    const newDate = new Date(viewYear, viewMonth, day);
    onDateChange(newDate);
    setShow(false);
  };

  const isDisabled = (day: number) => {
    if (!minimumDate) return false;
    const d = new Date(viewYear, viewMonth, day);
    const min = new Date(minimumDate.getFullYear(), minimumDate.getMonth(), minimumDate.getDate());
    return d < min;
  };

  const isSelected = (day: number) => {
    return date.getFullYear() === viewYear && date.getMonth() === viewMonth && date.getDate() === day;
  };

  const isToday = (day: number) => {
    const today = new Date();
    return today.getFullYear() === viewYear && today.getMonth() === viewMonth && today.getDate() === day;
  };

  const daysInMonth = getDaysInMonth(viewYear, viewMonth);
  const firstDay = getFirstDayOfMonth(viewYear, viewMonth);
  const calendarDays: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) calendarDays.push(null);
  for (let i = 1; i <= daysInMonth; i++) calendarDays.push(i);

  return (
    <View>
      <TouchableOpacity
        testID={`date-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
        style={styles.trigger}
        onPress={() => setShow(true)}
        activeOpacity={0.7}
      >
        <View style={[styles.dot, { backgroundColor: accentColor }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>{label}</Text>
          <Text style={styles.dateText}>{formatted}</Text>
        </View>
        <TouchableOpacity onPress={() => setShow(true)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Text style={[styles.changeBtn, { color: accentColor }]}>Change</Text>
        </TouchableOpacity>
      </TouchableOpacity>

      <Modal visible={show} transparent animationType="fade">
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShow(false)}>
          <View style={styles.calendarContainer} onStartShouldSetResponder={() => true}>
            {/* Header */}
            <View style={styles.calendarHeader}>
              <TouchableOpacity testID="prev-month-btn" onPress={prevMonth} style={styles.navBtn}>
                <Ionicons name="chevron-back" size={22} color="#0A0A0A" />
              </TouchableOpacity>
              <Text style={styles.monthYear}>{MONTHS[viewMonth]} {viewYear}</Text>
              <TouchableOpacity testID="next-month-btn" onPress={nextMonth} style={styles.navBtn}>
                <Ionicons name="chevron-forward" size={22} color="#0A0A0A" />
              </TouchableOpacity>
            </View>

            {/* Day headers */}
            <View style={styles.daysRow}>
              {DAYS_HEADER.map((d) => (
                <View key={d} style={styles.dayHeaderCell}>
                  <Text style={styles.dayHeaderText}>{d}</Text>
                </View>
              ))}
            </View>

            {/* Calendar grid */}
            <View style={styles.calendarGrid}>
              {calendarDays.map((day, idx) => (
                <View key={idx} style={styles.dayCell}>
                  {day ? (
                    <TouchableOpacity
                      testID={day ? `calendar-day-${day}` : undefined}
                      style={[
                        styles.dayButton,
                        isSelected(day) && { backgroundColor: accentColor },
                        isToday(day) && !isSelected(day) && styles.todayBtn,
                        isDisabled(day) && styles.disabledBtn,
                      ]}
                      onPress={() => !isDisabled(day) && selectDate(day)}
                      disabled={isDisabled(day)}
                    >
                      <Text style={[
                        styles.dayText,
                        isSelected(day) && styles.selectedDayText,
                        isDisabled(day) && styles.disabledDayText,
                        isToday(day) && !isSelected(day) && { color: accentColor, fontWeight: '800' },
                      ]}>
                        {day}
                      </Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              ))}
            </View>

            {/* Cancel button */}
            <TouchableOpacity testID="calendar-cancel-btn" style={styles.cancelBtn} onPress={() => setShow(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    padding: 16,
    borderRadius: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: '#E5E5E5',
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  label: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  dateText: { fontSize: 16, fontWeight: '700', color: '#0A0A0A', marginTop: 2 },
  changeBtn: { fontSize: 14, fontWeight: '700' },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  calendarContainer: {
    backgroundColor: '#FFF',
    borderRadius: 24,
    padding: 20,
    width: '100%',
    maxWidth: 380,
  },
  calendarHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  navBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  monthYear: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  daysRow: { flexDirection: 'row', marginBottom: 8 },
  dayHeaderCell: { flex: 1, alignItems: 'center', paddingVertical: 4 },
  dayHeaderText: { fontSize: 12, fontWeight: '700', color: '#999' },
  calendarGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  dayCell: { width: '14.28%', aspectRatio: 1, justifyContent: 'center', alignItems: 'center', padding: 2 },
  dayButton: { width: 38, height: 38, borderRadius: 19, justifyContent: 'center', alignItems: 'center' },
  dayText: { fontSize: 15, fontWeight: '600', color: '#0A0A0A' },
  selectedDayText: { color: '#FFF', fontWeight: '800' },
  todayBtn: { borderWidth: 1.5, borderColor: '#E5E5E5' },
  disabledBtn: { opacity: 0.3 },
  disabledDayText: { color: '#CCC' },
  cancelBtn: { marginTop: 12, alignItems: 'center', paddingVertical: 12 },
  cancelText: { fontSize: 16, fontWeight: '700', color: '#999' },
});
