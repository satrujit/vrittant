export default function SudokuPuzzle({ data: p }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{p.date}</div>
      <table className="border-collapse text-xs mx-auto">
        <tbody>
          {(p.value || []).map((row, i) => (
            <tr key={i}>{row.map((c, j) => (
              <td key={j} className={`w-7 h-7 text-center border border-gray-300 ${(i % 3 === 2 && i < 8) ? 'border-b-gray-700 border-b-2' : ''} ${(j % 3 === 2 && j < 8) ? 'border-r-gray-700 border-r-2' : ''} ${c ? 'font-semibold text-gray-900' : ''}`}>
                {c || ''}
              </td>
            ))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
