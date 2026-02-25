import { useNavigate } from 'react-router-dom'
import SchoolGradeInputModal from '../components/SchoolGradeInputModal'

export default function SchoolGradeInputPage() {
  const navigate = useNavigate()
  const handleClose = () => {
    if (window.history.length > 1) {
      navigate(-1)
      return
    }
    navigate('/chat')
  }

  return (
    <SchoolGradeInputModal
      isOpen
      embedded
      onClose={handleClose}
      onRequireSchoolRecordLink={() => navigate('/school-record-deep?tab=link')}
    />
  )
}
